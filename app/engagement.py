"""Who has gone quiet, and does the advisor need to know?

The second reason a multi-party agent is different: in a three-person financial
conversation the person who stops talking is usually the person who is about to
kill the deal, or the one being talked over. Nobody notices in the moment. The
earpiece can.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Role, Severity, Turn, Whisper

_NEGATIVE = {
    "worried", "worry", "nervous", "anxious", "scared", "afraid", "uncomfortable",
    "unsure", "hesitant", "confused", "lost", "concerned", "risky", "risk",
    "lose", "losing", "cant", "can't", "too much", "no", "not sure", "doubt",
}
_POSITIVE = {
    "great", "good", "happy", "excited", "makes sense", "perfect", "love",
    "comfortable", "confident", "yes", "agree", "sounds good", "clear",
}


@dataclass
class Participant:
    role: Role
    last_spoke_ms: int = 0
    turns: int = 0
    words: int = 0
    sentiment: float = 0.0   # rolling, -1..1
    nudged_at_ms: int = 0


@dataclass
class EngagementMonitor:
    """Tracks airtime and tone per participant."""

    silence_threshold_s: int = 90
    renudge_cooldown_s: int = 180
    participants: dict[Role, Participant] = field(default_factory=dict)

    def _p(self, role: Role) -> Participant:
        return self.participants.setdefault(role, Participant(role=role))

    @staticmethod
    def score_sentiment(text: str) -> float:
        low = f" {text.lower()} "
        neg = sum(1 for w in _NEGATIVE if f" {w} " in low or w in low)
        pos = sum(1 for w in _POSITIVE if f" {w} " in low or w in low)
        if neg == pos == 0:
            return 0.0
        return max(-1.0, min(1.0, (pos - neg) / float(pos + neg)))

    def observe(self, turn: Turn) -> None:
        p = self._p(turn.role)
        p.last_spoke_ms = turn.received_at_ms
        p.turns += 1
        p.words += len(turn.text.split())
        s = self.score_sentiment(turn.text)
        # Rolling average, weighted toward recent turns.
        p.sentiment = s if p.turns == 1 else (p.sentiment * 0.6 + s * 0.4)

    def check(self, now_ms: int) -> list[Whisper]:
        """Nudge about whoever has been quiet longest.

        At most one per check, deliberately. Two voices arriving in an earpiece
        at the same moment while the advisor is mid-sentence is not coaching,
        it is noise - and the advisor will pull the earpiece out.
        """
        out: list[Whisper] = []
        active = [p for p in self.participants.values() if p.role is not Role.UNKNOWN]
        if len(active) < 2:
            return out

        # Only meaningful once the call is actually underway.
        newest = max((p.last_spoke_ms for p in active), default=0)
        if not newest:
            return out

        candidates = [
            p
            for p in active
            if p.role is not Role.ADVISOR
            and p.turns > 0
            and (now_ms - p.last_spoke_ms) / 1000.0 >= self.silence_threshold_s
            and not (p.nudged_at_ms and (now_ms - p.nudged_at_ms) / 1000.0 < self.renudge_cooldown_s)
        ]
        candidates.sort(key=lambda p: p.last_spoke_ms)   # quietest longest, first

        for p in candidates[:1]:
            silent_s = (now_ms - p.last_spoke_ms) / 1000.0
            p.nudged_at_ms = now_ms

            mood = ""
            if p.sentiment <= -0.3:
                mood = " and their last few comments read as uneasy"
            out.append(
                Whisper(
                    headline=f"{p.role.value.title()} has been silent {int(silent_s)}s{mood}",
                    detail="Bring them in before moving on.",
                    severity=Severity.COACH,
                    suggested_phrasing=(
                        f"I want to make sure this works for both of you - "
                        f"how are you feeling about it so far?"
                    ),
                    rule_id="engagement-silence",
                )
            )
        return out

    def airtime(self) -> dict[str, float]:
        total = sum(p.words for p in self.participants.values()) or 1
        return {p.role.value: round(p.words / total, 3) for p in self.participants.values()}
