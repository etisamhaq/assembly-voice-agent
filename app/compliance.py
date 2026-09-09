"""Two-tier compliance detection.

Tier 1 - `RuleEngine`: deterministic patterns, sub-millisecond, runs on every
finalized turn. This is what meets the <1s whisper budget.

Tier 2 - `LLMJudge`: Claude reviewing the turn in conversational context. It
catches what patterns structurally cannot - an omitted risk disclosure, a
recommendation made before suitability was established, a promise implied
across two sentences. It runs concurrently and its findings arrive a beat
later, which is the correct tradeoff: a missed nuance whispered at 1.8s is
still useful, a missed "guaranteed" at 1.8s is not.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .models import Role, Severity, Turn, Violation

log = logging.getLogger("secondchair.compliance")

_SEVERITY = {s.value: s for s in Severity}


@dataclass
class Rule:
    id: str
    title: str
    severity: Severity
    regulation: str
    detail: str
    suggested_phrasing: str
    patterns: list[re.Pattern[str]]
    applies_to: set[Role]

    def match(self, text: str) -> str | None:
        for pat in self.patterns:
            m = pat.search(text)
            if m:
                return m.group(0).strip()
        return None


def load_rules(path: Path) -> list[Rule]:
    raw = yaml.safe_load(path.read_text())
    rules: list[Rule] = []
    for r in raw.get("rules", []):
        applies = r.get("applies_to") or ["advisor"]
        rules.append(
            Rule(
                id=r["id"],
                title=r["title"],
                severity=_SEVERITY.get(r.get("severity", "warning"), Severity.WARNING),
                regulation=r.get("regulation", ""),
                detail=r.get("detail", ""),
                suggested_phrasing=r.get("suggested_phrasing", ""),
                patterns=[re.compile(p, re.IGNORECASE) for p in r.get("patterns", [])],
                applies_to={Role(a) for a in applies},
            )
        )
    return rules


class RuleEngine:
    """Tier 1. Pure and synchronous - trivially testable, trivially fast."""

    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules

    @classmethod
    def from_path(cls, path: Path) -> "RuleEngine":
        return cls(load_rules(path))

    def scan(self, text: str, role: Role = Role.ADVISOR) -> list[Violation]:
        out: list[Violation] = []
        for rule in self.rules:
            if role not in rule.applies_to:
                continue
            quote = rule.match(text)
            if quote is None:
                continue
            out.append(
                Violation(
                    rule_id=rule.id,
                    title=rule.title,
                    severity=rule.severity,
                    regulation=rule.regulation,
                    detail=rule.detail,
                    suggested_phrasing=rule.suggested_phrasing,
                    source="rules",
                    confidence=1.0,
                    quote=quote,
                )
            )
        # Most severe first, so the whisper channel speaks the worst thing first.
        order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.COACH: 2, Severity.INFO: 3}
        out.sort(key=lambda v: order.get(v.severity, 9))
        return out


_JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "title": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "warning", "coach"]},
                    "regulation": {"type": "string"},
                    "detail": {"type": "string"},
                    "suggested_phrasing": {"type": "string"},
                    "quote": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "rule_id", "title", "severity", "regulation",
                    "detail", "suggested_phrasing", "quote", "confidence",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["violations"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM = """You are the compliance layer of Second Chair, a live assistant that sits in on \
retail investment advice conversations and warns the advisor through a private earpiece.

You review ONE advisor turn in context and report only violations that a regex cannot catch: \
omitted risk disclosure, a recommendation made before suitability was established, an implied \
promise spread across sentences, a misleading framing, a material question dodged.

Hard rules:
- The deterministic engine already caught the violations listed under ALREADY_CAUGHT. Never repeat those.
- Report nothing unless you are confident. An advisor who gets a false warning mid-sentence stops \
trusting the earpiece, and a distrusted earpiece is worse than no earpiece. Empty list is the \
common, correct answer.
- `suggested_phrasing` must be a sentence the advisor can say out loud immediately, in their voice, \
that fixes the problem. Not advice about what to do - the actual words.
- `detail` must be under 20 words. It is read aloud into someone's ear while they are mid-conversation.
- `quote` must be copied verbatim from the advisor turn.
- Text is PII-redacted; placeholders like [SSN_REDACTED] are expected and are not violations.
"""


class LLMJudge:
    """Tier 2. Optional - the product degrades to Tier 1 without an API key."""

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "claude-opus-5",
        effort: str = "low",
        timeout_s: float = 8.0,
    ) -> None:
        self.model = model
        self.effort = effort
        self.timeout_s = timeout_s
        self._client = None
        if api_key:
            try:
                import anthropic

                self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s)
            except ImportError:  # pragma: no cover
                log.warning("anthropic SDK not installed; LLM judge disabled")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def review(
        self,
        turn: Turn,
        text: str,
        history: Iterable[tuple[str, str]],
        already_caught: list[Violation],
    ) -> list[Violation]:
        if not self._client or turn.role is not Role.ADVISOR:
            return []

        transcript = "\n".join(f"{who}: {what}" for who, what in history)
        caught = ", ".join(v.rule_id for v in already_caught) or "none"
        prompt = (
            f"ALREADY_CAUGHT: {caught}\n\n"
            f"CONVERSATION SO FAR:\n{transcript or '(start of call)'}\n\n"
            f"ADVISOR TURN TO REVIEW:\n{text}"
        )

        try:
            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=[{"type": "text", "text": _JUDGE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": _JUDGE_SCHEMA},
                },
            )
        except Exception as exc:  # network, rate limit, refusal - never break the call
            log.warning("LLM judge unavailable for turn %s: %s", turn.turn_order, exc)
            return []

        if getattr(resp, "stop_reason", None) == "refusal":
            log.warning("LLM judge refused turn %s", turn.turn_order)
            return []

        try:
            block = next(b for b in resp.content if b.type == "text")
            data = json.loads(block.text)
        except (StopIteration, json.JSONDecodeError) as exc:
            log.warning("LLM judge returned unparseable output: %s", exc)
            return []

        seen = {v.rule_id for v in already_caught}
        out: list[Violation] = []
        for v in data.get("violations", []):
            if v.get("rule_id") in seen:
                continue
            out.append(
                Violation(
                    rule_id=v.get("rule_id", "llm-finding"),
                    title=v.get("title", "Compliance concern"),
                    severity=_SEVERITY.get(v.get("severity", "warning"), Severity.WARNING),
                    regulation=v.get("regulation", ""),
                    detail=v.get("detail", ""),
                    suggested_phrasing=v.get("suggested_phrasing", ""),
                    source="llm",
                    confidence=float(v.get("confidence", 0.5)),
                    quote=v.get("quote", ""),
                )
            )
        return out


class ComplianceEngine:
    """Fast path returns immediately; slow path is handed back as a task."""

    def __init__(self, rules: RuleEngine, judge: LLMJudge) -> None:
        self.rules = rules
        self.judge = judge

    def fast_scan(self, text: str, role: Role) -> tuple[list[Violation], int]:
        t0 = time.perf_counter()
        found = self.rules.scan(text, role)
        return found, int((time.perf_counter() - t0) * 1000)

    def escalate(
        self,
        turn: Turn,
        text: str,
        history: list[tuple[str, str]],
        already: list[Violation],
    ) -> asyncio.Task[list[Violation]] | None:
        if not self.judge.enabled or turn.role is not Role.ADVISOR:
            return None
        return asyncio.create_task(self.judge.review(turn, text, history, already))
