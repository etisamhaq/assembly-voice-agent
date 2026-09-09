"""Scripted replay source.

Not a mock in the throwaway sense - it is the harness the whole system is
developed and demoed against. It produces the same `Turn` objects the live
AssemblyAI source produces, including interim partials, so every downstream
stage runs its real code path.

Timestamps come from the script's own call timeline rather than the wall clock,
which means silence thresholds and engagement nudges behave identically at 1x
and at 50x. Tests run instantly; the demo runs in real time.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from ..models import Role, Turn
from .base import RoleResolver

DEFAULT_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "advisory_call.json"


class SimulatedSource:
    def __init__(
        self,
        script_path: Path | None = None,
        *,
        speed: float = 1.0,
        emit_partials: bool = True,
        epoch_ms: int = 0,
    ) -> None:
        self.script_path = Path(script_path or DEFAULT_SCRIPT)
        self.script: dict[str, Any] = json.loads(self.script_path.read_text())
        self.speed = max(speed, 0.0)
        self.emit_partials = emit_partials
        self.epoch_ms = epoch_ms
        self.resolver = RoleResolver()
        # The script declares ground-truth roles, so seed the resolver rather
        # than relying on speaking order.
        for label, meta in self.script.get("speakers", {}).items():
            self.resolver.override(label, Role(meta["role"]))
        self._closed = False

    @property
    def title(self) -> str:
        return self.script.get("title", "Simulated call")

    def speaker_name(self, label: str) -> str:
        return self.script.get("speakers", {}).get(label, {}).get("name", label)

    async def push_audio(self, chunk: bytes) -> None:
        """No-op: this source is its own audio."""

    async def close(self) -> None:
        self._closed = True

    async def _sleep(self, ms: float) -> None:
        if self.speed <= 0 or ms <= 0:
            return
        await asyncio.sleep((ms / 1000.0) / self.speed)

    async def stream(self) -> AsyncIterator[Turn]:
        prev_at = 0
        for order, entry in enumerate(self.script["turns"]):
            if self._closed:
                return

            at = int(entry["at"])
            await self._sleep(at - prev_at)
            prev_at = at

            label = entry["speaker"]
            role = self.resolver.resolve(label)
            text: str = entry["text"]
            # ~150 wpm is normal advisory-call pace.
            spoken_ms = max(900, int(len(text.split()) / 150 * 60_000))

            if self.emit_partials:
                words = text.split()
                for frac in (0.45, 0.8):
                    cut = max(1, int(len(words) * frac))
                    await self._sleep(spoken_ms * frac * 0.5)
                    yield Turn(
                        text=" ".join(words[:cut]),
                        speaker=label,
                        role=role,
                        turn_order=order,
                        start_ms=at,
                        end_ms=at + int(spoken_ms * frac),
                        end_of_turn=False,
                        confidence=0.4,
                        received_at_ms=self.epoch_ms + at + int(spoken_ms * frac),
                    )

            yield Turn(
                text=text,
                speaker=label,
                role=role,
                turn_order=order,
                start_ms=at,
                end_ms=at + spoken_ms,
                end_of_turn=True,
                confidence=0.93,
                received_at_ms=self.epoch_ms + at + spoken_ms,
            )
