"""AssemblyAI Universal-Streaming v3 source.

Connects to wss://streaming.assemblyai.com/v3/ws with streaming diarization on,
forwards raw PCM frames, and converts `Turn` messages into domain `Turn`s.

Two details that matter and are easy to get wrong:
  * The API key goes in the `Authorization` header with NO `Bearer` prefix.
  * Only `end_of_turn: true` messages are finalized. Partials are emitted for
    the live transcript view but must never reach the compliance path, or the
    advisor gets whispered at for half a sentence they were about to finish
    correctly.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from typing import AsyncIterator
from urllib.parse import urlencode

from ..models import Turn
from .base import RoleResolver

log = logging.getLogger("secondchair.assemblyai")

WS_BASE = "wss://streaming.assemblyai.com/v3/ws"


class AssemblyAIStreamingSource:
    def __init__(
        self,
        api_key: str,
        *,
        sample_rate: int = 16_000,
        max_speakers: int = 3,
        speech_model: str = "universal-3-5-pro",
        resolver: RoleResolver | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is required for the live source")
        self.api_key = api_key
        self.sample_rate = sample_rate
        self.max_speakers = max_speakers
        self.speech_model = speech_model
        self.resolver = resolver or RoleResolver()
        self._ws = None
        self._audio: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=256)
        self._closed = False
        self.session_id: str | None = None

    @property
    def url(self) -> str:
        params = {
            "sample_rate": self.sample_rate,
            "speech_model": self.speech_model,
            "speaker_labels": "true",
            "max_speakers": self.max_speakers,
            "format_turns": "true",
        }
        return f"{WS_BASE}?{urlencode(params)}"

    async def push_audio(self, chunk: bytes) -> None:
        if self._closed:
            return
        try:
            self._audio.put_nowait(chunk)
        except asyncio.QueueFull:
            # Dropping the oldest frame beats growing latency without bound.
            try:
                self._audio.get_nowait()
                self._audio.put_nowait(chunk)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass

    async def _pump_audio(self) -> None:
        assert self._ws is not None
        while not self._closed:
            chunk = await self._audio.get()
            if chunk is None:
                break
            try:
                await self._ws.send(chunk)
            except Exception as exc:
                log.warning("audio send failed: %s", exc)
                break

    @staticmethod
    def _dominant_speaker(msg: dict) -> str:
        """Per-word labels -> the speaker who owns this turn."""
        words = msg.get("words") or []
        labels = [w.get("speaker") for w in words if w.get("speaker")]
        if labels:
            return Counter(labels).most_common(1)[0][0]
        return msg.get("speaker") or "SPEAKER_A"

    def _to_turn(self, msg: dict) -> Turn:
        words = msg.get("words") or []
        speaker = self._dominant_speaker(msg)
        return Turn(
            text=(msg.get("transcript") or "").strip(),
            speaker=speaker,
            role=self.resolver.resolve(speaker),
            turn_order=int(msg.get("turn_order", 0)),
            start_ms=int(words[0]["start"]) if words else 0,
            end_ms=int(words[-1]["end"]) if words else 0,
            end_of_turn=bool(msg.get("end_of_turn", False)),
            confidence=float(msg.get("end_of_turn_confidence", 1.0)),
        )

    async def stream(self) -> AsyncIterator[Turn]:
        import websockets

        async with websockets.connect(
            self.url,
            additional_headers={"Authorization": self.api_key},  # no "Bearer"
            ping_interval=20,
            max_size=None,
        ) as ws:
            self._ws = ws
            pump = asyncio.create_task(self._pump_audio())
            try:
                async for raw in ws:
                    if isinstance(raw, (bytes, bytearray)):
                        continue
                    msg = json.loads(raw)
                    kind = msg.get("type")
                    if kind == "Begin":
                        self.session_id = msg.get("id")
                        log.info("streaming session %s open", self.session_id)
                    elif kind == "Turn":
                        turn = self._to_turn(msg)
                        if turn.text:
                            yield turn
                    elif kind == "Termination":
                        log.info(
                            "session closed after %.1fs audio",
                            msg.get("audio_duration_seconds", 0.0),
                        )
                        break
                    elif kind == "Error":
                        log.error("stream error: %s", msg)
            finally:
                self._closed = True
                await self._audio.put(None)
                pump.cancel()
                self._ws = None

    async def close(self) -> None:
        self._closed = True
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "Terminate"}))
            except Exception:
                pass
