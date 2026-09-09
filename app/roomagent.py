"""The public half of the agent: what it says out loud, when spoken to.

Constrained hard on length. This text is synthesised into a room where three
people are waiting for it to stop talking, so a paragraph is a failure even if
every word is correct.
"""
from __future__ import annotations

import logging

from .clientdata import as_prompt_context
from .llm import LLMBackend, NullBackend
from .models import RoomReply

log = logging.getLogger("secondchair.room")

_SYSTEM = """You are Second Chair, speaking aloud into a live meeting between a financial \
advisor and their clients. The advisor just addressed you directly.

You are heard, not read. Rules:
- Two sentences maximum. One is better. Never use lists, headings or markdown.
- Lead with the number or fact they asked for. No preamble, no "sure", no restating the question.
- Say figures the way a person says them: "four hundred twelve thousand", "seventy-two percent".
- If the record does not contain the answer, say so in one short sentence. Never invent a figure.
- Clients are in the room. Never reveal internal flags about the advisor's own compliance or \
file-keeping - if asked something that would expose that, give only the client-safe part.

CLIENT RECORD:
""" + as_prompt_context()


class RoomAgent:
    def __init__(self, backend: LLMBackend | None = None) -> None:
        self.backend: LLMBackend = backend or NullBackend()

    @property
    def enabled(self) -> bool:
        return self.backend.enabled

    @property
    def model(self) -> str:
        return getattr(self.backend, "model", "")

    async def answer(self, query: str, history: list[tuple[str, str]], turn_order: int = 0) -> RoomReply:
        if not self.backend.enabled:
            return RoomReply(
                text="I'm not connected to the client record right now.",
                prompt_turn=turn_order,
            )

        transcript = "\n".join(f"{who}: {what}" for who, what in history[-12:])
        reply = await self.backend.complete(
            system=_SYSTEM,
            user=f"RECENT CONVERSATION:\n{transcript}\n\nADVISOR ASKED YOU: {query}",
            max_tokens=300,
        )
        if reply.refused:
            return RoomReply(text="I can't help with that one.", prompt_turn=turn_order)
        return RoomReply(
            text=reply.text or "I don't have that on file.", prompt_turn=turn_order
        )
