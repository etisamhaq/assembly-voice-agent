"""Transcript source contract.

Both sources yield identical `Turn` objects, so every stage downstream -
redaction, compliance, addressivity, audit - is exercised the same way whether
the audio came from a microphone or from a script. That is what makes this
system testable without an API key or a three-person room.
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol

from ..models import Role, Turn


class TranscriptSource(Protocol):
    async def stream(self) -> AsyncIterator[Turn]: ...
    async def push_audio(self, chunk: bytes) -> None: ...
    async def close(self) -> None: ...


class RoleResolver:
    """Maps raw diarization labels (SPEAKER_A...) onto roles in the room.

    Live diarization gives you consistent-but-anonymous labels; it cannot know
    which voice is the advisor. The convention here: whoever speaks first is
    the advisor (they open the meeting and they are the one wearing the
    earpiece). Later speakers fill the remaining seats in order. The UI can
    override any assignment mid-call.
    """

    def __init__(self, seats: tuple[Role, ...] = (Role.ADVISOR, Role.CLIENT, Role.SPOUSE)) -> None:
        self.seats = seats
        self._map: dict[str, Role] = {}

    def peek(self, speaker: str | None) -> Role | None:
        """The role already assigned to a label, without claiming a seat."""
        return self._map.get(speaker) if speaker else None

    def seat(self, speaker: str) -> Role:
        """Claim the next seat for a diarization label.

        Only ever call this for a real label on a finalized turn. Seating from
        a partial - or from a synthetic placeholder used before diarization has
        settled - burns the advisor seat on a speaker who does not exist, and
        every real person then shifts one seat down.
        """
        if speaker in self._map:
            return self._map[speaker]
        idx = len(self._map)
        role = self.seats[idx] if idx < len(self.seats) else Role.UNKNOWN
        self._map[speaker] = role
        return role

    def resolve(self, speaker: str) -> Role:
        """Backwards-compatible alias for `seat`."""
        return self.seat(speaker)

    def override(self, speaker: str, role: Role) -> None:
        self._map[speaker] = role

    def assignments(self) -> dict[str, str]:
        return {k: v.value for k, v in self._map.items()}
