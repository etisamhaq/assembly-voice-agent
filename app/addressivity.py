"""Was that said *to* the agent?

The hard problem in a multi-party room. A two-party voice agent can assume
every utterance is for it. Second Chair cannot: most of what it hears is two
humans talking to each other, and an agent that answers those is worse than
useless - it is an interruption in someone's meeting.

Three signals, cheapest first:
  1. Vocative address - the wake term used to summon, not to describe.
  2. Follow-up window - the agent just spoke and the advisor is continuing.
  3. Everything else - silence.

Deliberately biased toward silence. A missed summons costs one repeat; a false
positive costs the advisor's credibility in front of their client.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Role, Turn

WAKE_TERMS = ("second chair", "secondchair", "second-chair")
_SHORT_WAKE = re.compile(r"\b(?:hey|ok|okay)[, ]+chair\b", re.IGNORECASE)

# "Second Chair, pull up..." / "...what do you think, Second Chair?"
_VOCATIVE_LEAD = re.compile(
    r"^\s*(?:hey|ok|okay|so|and)?[, ]*(?:%s)\b[,:]?\s+(?P<rest>.+)$" % "|".join(WAKE_TERMS),
    re.IGNORECASE | re.DOTALL,
)
_VOCATIVE_TRAIL = re.compile(
    r"(?P<rest>.+?)[,\s]+(?:%s)\s*[?.!]?\s*$" % "|".join(WAKE_TERMS),
    re.IGNORECASE | re.DOTALL,
)

# The wake term as a subject/object rather than a summons.
_THIRD_PERSON = re.compile(
    r"\b(?:%s)\b\s+(?:is|was|will|would|can|could|does|did|has|had|helps?|listens?|records?|and)\b"
    % "|".join(WAKE_TERMS),
    re.IGNORECASE,
)
_POSSESSIVE = re.compile(r"\b(?:%s)(?:'s|s')\b" % "|".join(WAKE_TERMS), re.IGNORECASE)

# A bare command verb opening the remainder ("pull up...", "check...").
_IMPERATIVE_LEAD = re.compile(
    r"^\s*(?:please\s+)?(?:pull|show|find|look|check|read|tell|give|remind|bring|open|search|"
    r"list|get|confirm|summar\w+|calculate|compare|remind|note|log|flag)\b",
    re.IGNORECASE,
)

_REQUEST = re.compile(
    r"\b(?:what|what's|whats|when|where|which|who|why|how|can|could|would|will|do|does|did|is|are|"
    r"pull|show|find|look|check|read|tell|give|remind|bring|open|search|list|get|confirm|"
    r"summar\w+|calculate|compare)\b",
    re.IGNORECASE,
)


@dataclass
class Addressivity:
    addressed: bool
    confidence: float
    reason: str
    query: str = ""      # the turn with the vocative stripped, ready for the agent


def _strip_wake(text: str) -> str:
    m = _VOCATIVE_LEAD.match(text)
    if m:
        return m.group("rest").strip()
    m = _VOCATIVE_TRAIL.match(text)
    if m:
        return m.group("rest").strip()
    out = text
    for term in WAKE_TERMS:
        out = re.sub(r"\b%s\b[,:]?" % re.escape(term), "", out, flags=re.IGNORECASE)
    return _SHORT_WAKE.sub("", out).strip(" ,.")


class AddressivityDetector:
    def __init__(
        self,
        *,
        followup_window_s: float = 12.0,
        allow_roles: tuple[Role, ...] = (Role.ADVISOR,),
    ) -> None:
        self.followup_window_s = followup_window_s
        self.allow_roles = allow_roles
        self._agent_last_spoke_ms: int | None = None

    def note_agent_spoke(self, at_ms: int) -> None:
        self._agent_last_spoke_ms = at_ms

    def evaluate(self, turn: Turn) -> Addressivity:
        text = (turn.text or "").strip()
        if not text:
            return Addressivity(False, 1.0, "empty")

        lowered = text.lower()
        has_wake = any(t in lowered for t in WAKE_TERMS) or bool(_SHORT_WAKE.search(text))

        if has_wake:
            # "Second Chair is recording this" - describing the agent, not calling it.
            if _THIRD_PERSON.search(text) or _POSSESSIVE.search(text):
                # Only a genuine question or a command overrides the descriptive
                # reading. "Second Chair is recording this" is about the agent;
                # "Second Chair can you check X?" is to it.
                rest = _strip_wake(text)
                interrogative = text.rstrip().endswith("?")
                commanding = bool(_IMPERATIVE_LEAD.match(rest))
                if not (interrogative or commanding):
                    return Addressivity(False, 0.85, "wake term used descriptively")

            if turn.role not in self.allow_roles and turn.role is not Role.UNKNOWN:
                return Addressivity(False, 0.7, f"{turn.role.value} may not command the agent")

            query = _strip_wake(text)
            if not query:
                return Addressivity(True, 0.6, "bare summons", query="")
            return Addressivity(True, 0.95, "vocative address", query=query)

        # No wake term: only a follow-up inside the window can qualify.
        if self._agent_last_spoke_ms is None or turn.role not in self.allow_roles:
            return Addressivity(False, 0.99, "no wake term")

        gap_s = (turn.received_at_ms - self._agent_last_spoke_ms) / 1000.0
        if 0 <= gap_s <= self.followup_window_s and _REQUEST.search(text) and "?" in text:
            return Addressivity(True, 0.65, f"follow-up {gap_s:.1f}s after agent reply", query=text)

        return Addressivity(False, 0.9, "no wake term")
