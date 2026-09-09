"""Core domain objects shared by every stage of the pipeline.

The pipeline is deliberately built around plain dataclasses rather than the
transport types of any one vendor, so the AssemblyAI source and the simulated
source feed byte-identical objects into the compliance path.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def _id() -> str:
    return uuid.uuid4().hex[:12]


class Role(str, Enum):
    """Who a diarized speaker maps to in the room."""

    ADVISOR = "advisor"      # the professional wearing the earpiece
    CLIENT = "client"
    SPOUSE = "spouse"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    CRITICAL = "critical"    # regulatory violation, interrupt immediately
    WARNING = "warning"      # risky phrasing, worth a nudge
    COACH = "coach"          # opportunity, not a problem
    INFO = "info"


class Channel(str, Enum):
    WHISPER = "whisper"      # private, advisor's earpiece only
    ROOM = "room"            # spoken aloud to everyone


@dataclass
class Turn:
    """One finalized (or in-progress) speaker turn."""

    text: str
    speaker: str = "SPEAKER_A"          # raw diarization label
    role: Role = Role.UNKNOWN           # resolved role
    turn_order: int = 0
    start_ms: int = 0
    end_ms: int = 0
    end_of_turn: bool = True
    confidence: float = 1.0
    received_at_ms: int = field(default_factory=_now_ms)

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass
class Redaction:
    kind: str                 # ssn | credit_card | phone | email | dob | account
    placeholder: str
    count: int = 1


@dataclass
class Violation:
    rule_id: str
    title: str
    severity: Severity
    regulation: str
    detail: str
    suggested_phrasing: str = ""
    source: str = "rules"     # rules | llm
    confidence: float = 1.0
    quote: str = ""


@dataclass
class Whisper:
    """A message for the advisor's ear only."""

    headline: str
    detail: str = ""
    severity: Severity = Severity.INFO
    suggested_phrasing: str = ""
    rule_id: str = ""
    latency_ms: int = 0
    # 1 = deterministic fast path, held to the whisper budget.
    # 2 = detached LLM escalation, expected to land later by design.
    tier: int = 1
    id: str = field(default_factory=_id)


@dataclass
class RoomReply:
    """Something the agent says out loud, because it was addressed."""

    text: str
    prompt_turn: int = 0
    latency_ms: int = 0
    id: str = field(default_factory=_id)


@dataclass
class PipelineResult:
    """Everything one turn produced. Purely descriptive - no I/O."""

    turn: Turn
    redacted_text: str
    redactions: list[Redaction] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    whispers: list[Whisper] = field(default_factory=list)
    room_reply: RoomReply | None = None
    addressed_to_agent: bool = False
    fast_path_ms: int = 0
    # perf_counter() at ingest. Turn timestamps may be on a simulated call
    # timeline, so late-arriving stages must measure against this, not against
    # wall-clock minus a turn timestamp.
    ingested_at: float = 0.0

    def to_event(self) -> dict[str, Any]:
        return {
            "type": "turn.processed",
            "turn": {
                "order": self.turn.turn_order,
                "speaker": self.turn.speaker,
                "role": self.turn.role.value,
                "text": self.redacted_text,
                "start_ms": self.turn.start_ms,
                "end_ms": self.turn.end_ms,
                "confidence": round(self.turn.confidence, 3),
            },
            "redactions": [{"kind": r.kind, "count": r.count} for r in self.redactions],
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "title": v.title,
                    "severity": v.severity.value,
                    "regulation": v.regulation,
                    "detail": v.detail,
                    "suggested_phrasing": v.suggested_phrasing,
                    "source": v.source,
                    "quote": v.quote,
                }
                for v in self.violations
            ],
            "addressed_to_agent": self.addressed_to_agent,
            "fast_path_ms": self.fast_path_ms,
        }
