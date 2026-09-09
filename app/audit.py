"""Append-only, PII-free, speaker-attributed session record.

This is the artefact a compliance officer actually keeps. It only ever receives
redacted text - `Pipeline` has no code path that writes raw transcript here.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import PipelineResult, Whisper


def _enc(o: Any) -> Any:
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    if hasattr(o, "value"):
        return o.value
    return str(o)


class AuditLog:
    def __init__(self, directory: Path, session_id: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.path = self.directory / f"session-{session_id}.jsonl"
        self.started_at = time.time()
        self._counts: dict[str, int] = {}
        self._write({"event": "session.start", "session_id": session_id})

    def _write(self, payload: dict[str, Any]) -> None:
        payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=_enc) + "\n")
        self._counts[payload["event"]] = self._counts.get(payload["event"], 0) + 1

    def record_turn(self, result: PipelineResult) -> None:
        self._write(
            {
                "event": "turn",
                "order": result.turn.turn_order,
                "role": result.turn.role.value,
                "speaker": result.turn.speaker,
                "start_ms": result.turn.start_ms,
                "end_ms": result.turn.end_ms,
                "text": result.redacted_text,          # redacted only
                "redactions": [{"kind": r.kind, "count": r.count} for r in result.redactions],
                "violations": [
                    {
                        "rule_id": v.rule_id,
                        "severity": v.severity.value,
                        "regulation": v.regulation,
                        "quote": v.quote,
                        "source": v.source,
                    }
                    for v in result.violations
                ],
                "addressed_to_agent": result.addressed_to_agent,
            }
        )

    def record_whisper(self, w: Whisper) -> None:
        self._write(
            {
                "event": "whisper",
                "rule_id": w.rule_id,
                "severity": w.severity.value,
                "headline": w.headline,
                "latency_ms": w.latency_ms,
            }
        )

    def record_room_reply(self, text: str, latency_ms: int) -> None:
        self._write({"event": "room_reply", "text": text, "latency_ms": latency_ms})

    def close(self, summary: dict[str, Any] | None = None) -> dict[str, Any]:
        out = {
            "event": "session.end",
            "session_id": self.session_id,
            "duration_s": round(time.time() - self.started_at, 2),
            "counts": dict(self._counts),
            **(summary or {}),
        }
        self._write(out)
        return out
