"""The public half of the agent: what it says out loud, when spoken to.

Constrained hard on length. This text is synthesised into a room where three
people are waiting for it to stop talking, so a paragraph is a failure even if
every word is correct.
"""
from __future__ import annotations

import logging

from .clientdata import as_prompt_context
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
    def __init__(self, *, api_key: str = "", model: str = "claude-opus-5", timeout_s: float = 10.0) -> None:
        self.model = model
        self._client = None
        if api_key:
            try:
                import anthropic

                self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s)
            except ImportError:  # pragma: no cover
                log.warning("anthropic SDK not installed; room agent disabled")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def answer(self, query: str, history: list[tuple[str, str]], turn_order: int = 0) -> RoomReply:
        if not self._client:
            return RoomReply(
                text="I'm not connected to the client record right now.",
                prompt_turn=turn_order,
            )

        transcript = "\n".join(f"{who}: {what}" for who, what in history[-12:])
        try:
            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=300,
                system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[
                    {
                        "role": "user",
                        "content": f"RECENT CONVERSATION:\n{transcript}\n\nADVISOR ASKED YOU: {query}",
                    }
                ],
                output_config={"effort": "low"},
            )
        except Exception as exc:
            log.warning("room agent failed: %s", exc)
            return RoomReply(text="I couldn't reach the record just then.", prompt_turn=turn_order)

        if getattr(resp, "stop_reason", None) == "refusal":
            return RoomReply(text="I can't help with that one.", prompt_turn=turn_order)

        text = " ".join(b.text for b in resp.content if b.type == "text").strip()
        return RoomReply(text=text or "I don't have that on file.", prompt_turn=turn_order)
