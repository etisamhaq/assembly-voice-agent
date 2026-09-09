"""The orchestrator.

One finalized turn flows through here in a fixed order:

    redact -> fast compliance scan -> whisper  (the <1s path, all local)
           -> addressivity -> room reply       (only if addressed)
           -> engagement check
           -> audit
           +> LLM judge escalation             (concurrent, lands later)

The ordering is the product. Redaction is first because nothing downstream may
see raw PII. The fast scan is second because the whisper budget is the one
number that decides whether the earpiece is useful. The LLM judge is detached
because correctness that arrives late is still worth having, but it must never
be able to delay a "you just said guaranteed" warning.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Iterable

from .addressivity import AddressivityDetector
from .audit import AuditLog
from .compliance import ComplianceEngine
from .engagement import EngagementMonitor
from .guardrails import LocalRedactor, Redactor
from .models import (
    Channel,
    PipelineResult,
    Role,
    RoomReply,
    Severity,
    Turn,
    Violation,
    Whisper,
)
from .roomagent import RoomAgent

log = logging.getLogger("secondchair.pipeline")

Emit = Callable[[dict], Awaitable[None]]

_SEVERITY_RANK = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.COACH: 2, Severity.INFO: 3}


def violation_to_whisper(v: Violation, latency_ms: int) -> Whisper:
    return Whisper(
        headline=v.title,
        detail=v.detail,
        severity=v.severity,
        suggested_phrasing=v.suggested_phrasing,
        rule_id=v.rule_id,
        latency_ms=latency_ms,
    )


class Pipeline:
    def __init__(
        self,
        *,
        compliance: ComplianceEngine,
        room_agent: RoomAgent,
        emit: Emit,
        redactor: Redactor | None = None,
        addressivity: AddressivityDetector | None = None,
        engagement: EngagementMonitor | None = None,
        audit: AuditLog | None = None,
        whisper_budget_ms: int = 1000,
        history_limit: int = 24,
    ) -> None:
        self.compliance = compliance
        self.room_agent = room_agent
        self.emit = emit
        self.redactor = redactor or LocalRedactor()
        self.addressivity = addressivity or AddressivityDetector()
        self.engagement = engagement or EngagementMonitor()
        self.audit = audit
        self.whisper_budget_ms = whisper_budget_ms
        self.history_limit = history_limit

        self.history: list[tuple[str, str]] = []
        self.results: list[PipelineResult] = []
        self._pending: set[asyncio.Task] = set()
        self.stats = {
            "turns": 0,
            "violations": 0,
            "whispers": 0,
            "room_replies": 0,
            "redactions": 0,
            "budget_misses": 0,
            "max_fast_path_ms": 0,
        }

    # ------------------------------------------------------------------ emit

    async def _send_whisper(self, w: Whisper) -> None:
        self.stats["whispers"] += 1
        if w.latency_ms > self.whisper_budget_ms:
            self.stats["budget_misses"] += 1
        if self.audit:
            self.audit.record_whisper(w)
        await self.emit(
            {
                "type": "whisper",
                "channel": Channel.WHISPER.value,
                "id": w.id,
                "severity": w.severity.value,
                "headline": w.headline,
                "detail": w.detail,
                "suggested_phrasing": w.suggested_phrasing,
                "rule_id": w.rule_id,
                "latency_ms": w.latency_ms,
                "over_budget": w.latency_ms > self.whisper_budget_ms,
            }
        )

    async def _send_room(self, reply: RoomReply) -> None:
        self.stats["room_replies"] += 1
        self.addressivity.note_agent_spoke(int(time.time() * 1000))
        if self.audit:
            self.audit.record_room_reply(reply.text, reply.latency_ms)
        self.history.append(("Second Chair", reply.text))
        await self.emit(
            {
                "type": "room",
                "channel": Channel.ROOM.value,
                "id": reply.id,
                "text": reply.text,
                "latency_ms": reply.latency_ms,
            }
        )

    # -------------------------------------------------------------- ingestion

    async def handle_turn(self, turn: Turn) -> PipelineResult | None:
        """Partials update the transcript view; only finals are acted on."""
        if not turn.end_of_turn:
            await self.emit(
                {
                    "type": "transcript.partial",
                    "order": turn.turn_order,
                    "role": turn.role.value,
                    "speaker": turn.speaker,
                    "text": self.redactor.redact(turn.text)[0],
                }
            )
            return None

        t0 = time.perf_counter()

        # 1. Redact before anything else touches the text.
        redacted, redactions = self.redactor.redact(turn.text)

        # 2. Fast compliance scan.
        violations, scan_ms = self.compliance.fast_scan(redacted, turn.role)

        result = PipelineResult(
            turn=turn,
            redacted_text=redacted,
            redactions=redactions,
            violations=list(violations),
        )

        # 3. Whisper immediately - this is the latency-critical emission.
        for v in violations:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            w = violation_to_whisper(v, latency_ms)
            result.whispers.append(w)
            await self._send_whisper(w)

        result.fast_path_ms = int((time.perf_counter() - t0) * 1000)
        self.stats["max_fast_path_ms"] = max(self.stats["max_fast_path_ms"], result.fast_path_ms)
        self.stats["turns"] += 1
        self.stats["violations"] += len(violations)
        self.stats["redactions"] += sum(r.count for r in redactions)

        # 4. Bookkeeping that the later stages read from.
        self.history.append((turn.role.value, redacted))
        self.history[:] = self.history[-self.history_limit :]
        self.engagement.observe(turn)

        # 5. Addressivity - does the agent speak out loud?
        verdict = self.addressivity.evaluate(turn)
        result.addressed_to_agent = verdict.addressed
        await self.emit(result.to_event())

        if verdict.addressed:
            r0 = time.perf_counter()
            reply = await self.room_agent.answer(
                verdict.query or redacted, self.history, turn.turn_order
            )
            reply.latency_ms = int((time.perf_counter() - r0) * 1000)
            result.room_reply = reply
            await self._send_room(reply)

        # 6. Engagement nudges, on the source's clock.
        for nudge in self.engagement.check(turn.received_at_ms):
            result.whispers.append(nudge)
            await self._send_whisper(nudge)

        # 7. Audit, then detach the LLM judge.
        if self.audit:
            self.audit.record_turn(result)

        task = self.compliance.escalate(turn, redacted, list(self.history), list(violations))
        if task is not None:
            self._pending.add(task)
            task.add_done_callback(self._pending.discard)
            task.add_done_callback(
                lambda t, _r=result: asyncio.create_task(self._on_escalation(t, _r))
            )

        self.results.append(result)
        return result

    async def _on_escalation(self, task: "asyncio.Task[list[Violation]]", result: PipelineResult) -> None:
        try:
            extra = task.result()
        except (asyncio.CancelledError, Exception) as exc:  # noqa: BLE001
            log.debug("escalation dropped: %s", exc)
            return
        if not extra:
            return
        extra.sort(key=lambda v: _SEVERITY_RANK.get(v.severity, 9))
        elapsed = int(time.time() * 1000) - result.turn.received_at_ms
        for v in extra:
            result.violations.append(v)
            self.stats["violations"] += 1
            w = violation_to_whisper(v, max(elapsed, 0))
            result.whispers.append(w)
            await self._send_whisper(w)

    # ------------------------------------------------------------------- run

    async def run(self, source) -> dict:
        await self.emit({"type": "session.state", "state": "listening"})
        try:
            async for turn in source.stream():
                await self.handle_turn(turn)
        finally:
            if self._pending:
                await asyncio.gather(*list(self._pending), return_exceptions=True)
                await asyncio.sleep(0)  # let escalation callbacks drain
        summary = self.summary()
        await self.emit({"type": "session.end", **summary})
        return summary

    def summary(self) -> dict:
        by_sev: dict[str, int] = {}
        for r in self.results:
            for v in r.violations:
                by_sev[v.severity.value] = by_sev.get(v.severity.value, 0) + 1
        return {
            **self.stats,
            "violations_by_severity": by_sev,
            "airtime": self.engagement.airtime(),
        }
