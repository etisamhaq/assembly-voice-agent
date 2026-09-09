"""FastAPI app: static UI, control endpoints, and the session WebSocket."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .addressivity import AddressivityDetector
from .audit import AuditLog
from .channels import TTS, whisper_speech
from .compliance import ComplianceEngine, RuleEngine
from .config import WEB_DIR, settings
from .engagement import EngagementMonitor
from .factory import build_judge, build_room_agent
from .models import Channel
from .pipeline import Pipeline
from .sources.assemblyai import AssemblyAIStreamingSource
from .sources.simulated import SimulatedSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("secondchair")

app = FastAPI(title="Second Chair", version="1.0.0")

_rules = RuleEngine.from_path(settings.rules_path)


def build_tts() -> TTS:
    return TTS(
        api_key=settings.elevenlabs_key,
        whisper_voice_id=settings.whisper_voice_id,
        room_voice_id=settings.room_voice_id,
    )


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "rules_loaded": len(_rules.rules),
            "capabilities": {
                "live_audio": settings.live_audio_enabled,
                "llm_judge": settings.llm_enabled,
                "room_agent": settings.llm_enabled,
                "server_tts": settings.tts_enabled,
            },
            "models": {"judge": settings.judge_model, "room": settings.room_model},
            "llm_backend": build_judge().backend.name,
            "default_source": settings.source,
            "whisper_budget_ms": settings.whisper_budget_ms,
        }
    )


@app.get("/api/rules")
async def rules() -> JSONResponse:
    return JSONResponse(
        {
            "rules": [
                {
                    "id": r.id,
                    "title": r.title,
                    "severity": r.severity.value,
                    "regulation": r.regulation,
                    "applies_to": sorted(x.value for x in r.applies_to),
                    "patterns": len(r.patterns),
                }
                for r in _rules.rules
            ]
        }
    )


@app.get("/api/script")
async def script() -> JSONResponse:
    src = SimulatedSource(speed=0)
    return JSONResponse({"title": src.title, "script": src.script})


class Session:
    """One call. Owns the pipeline, the source, and the socket."""

    def __init__(self, ws: WebSocket, *, mode: str, speed: float) -> None:
        self.ws = ws
        self.mode = mode
        self.speed = speed
        self.id = uuid.uuid4().hex[:8]
        self.tts = build_tts()
        self.audit = AuditLog(settings.audit_dir, self.id)
        self.source = None
        self._closed = False

        self.pipeline = Pipeline(
            compliance=ComplianceEngine(_rules, build_judge()),
            room_agent=build_room_agent(),
            emit=self.emit,
            addressivity=AddressivityDetector(),
            engagement=EngagementMonitor(silence_threshold_s=settings.silence_nudge_seconds),
            audit=self.audit,
            whisper_budget_ms=settings.whisper_budget_ms,
        )

    async def emit(self, event: dict) -> None:
        if self._closed:
            return
        # Attach synthesized audio for the two speaking channels.
        if self.tts.enabled:
            if event.get("type") == "whisper":
                event["audio_b64"] = await self.tts.synthesize(
                    whisper_speech(event["headline"], event["detail"], event["suggested_phrasing"]),
                    Channel.WHISPER,
                )
            elif event.get("type") == "room":
                event["audio_b64"] = await self.tts.synthesize(event["text"], Channel.ROOM)
        try:
            await self.ws.send_text(json.dumps(event))
        except (WebSocketDisconnect, RuntimeError):
            self._closed = True

    def build_source(self):
        if self.mode == "live":
            if not settings.live_audio_enabled:
                raise RuntimeError("ASSEMBLYAI_API_KEY is not set - live mode unavailable")
            return AssemblyAIStreamingSource(
                settings.assemblyai_key,
                sample_rate=settings.sample_rate,
                max_speakers=settings.max_speakers,
            )
        return SimulatedSource(speed=self.speed)

    async def run(self) -> None:
        self.source = self.build_source()
        await self.emit(
            {
                "type": "session.begin",
                "session_id": self.id,
                "mode": self.mode,
                "title": getattr(self.source, "title", "Live call"),
                "capabilities": {
                    "llm_judge": self.pipeline.compliance.judge.enabled,
                    "room_agent": self.pipeline.room_agent.enabled,
                    "server_tts": self.tts.enabled,
                },
            }
        )
        summary = await self.pipeline.run(self.source)
        self.audit.close(summary)
        await self.emit(
            {"type": "audit.ready", "path": str(self.audit.path), "session_id": self.id}
        )

    async def close(self) -> None:
        self._closed = True
        if self.source is not None:
            with suppress(Exception):
                await self.source.close()


@app.websocket("/ws/session")
async def session_socket(ws: WebSocket) -> None:
    await ws.accept()
    params = ws.query_params
    mode = params.get("mode", "simulated")
    try:
        speed = float(params.get("speed", "1"))
    except ValueError:
        speed = 1.0

    session = Session(ws, mode=mode, speed=speed)
    runner = asyncio.create_task(session.run())

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            # Binary frames are microphone audio destined for the live source.
            if (data := msg.get("bytes")) is not None and session.source is not None:
                await session.source.push_audio(data)
            elif (text := msg.get("text")) is not None:
                with suppress(json.JSONDecodeError):
                    payload = json.loads(text)
                    if payload.get("type") == "stop":
                        break
    except WebSocketDisconnect:
        pass
    finally:
        await session.close()
        runner.cancel()
        with suppress(asyncio.CancelledError):
            await runner


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
