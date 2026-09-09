"""The two output channels.

The whole conceit of Second Chair is that it has two mouths:

  WHISPER - private, in the advisor's earpiece. Nobody else hears it.
  ROOM    - spoken aloud, and only ever when the agent was addressed.

Server-side synthesis is optional. Without an ElevenLabs key the channels stay
text-only and the browser falls back to local speech synthesis, panned hard
left for whisper and centre for room - which is what actually makes the
distinction legible to someone wearing headphones.
"""
from __future__ import annotations

import base64
import logging

from .models import Channel

log = logging.getLogger("secondchair.channels")

_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


class TTS:
    def __init__(
        self,
        *,
        api_key: str = "",
        whisper_voice_id: str = "",
        room_voice_id: str = "",
        model_id: str = "eleven_flash_v2_5",   # lowest first-byte latency
        timeout_s: float = 6.0,
    ) -> None:
        self.api_key = api_key
        self.whisper_voice_id = whisper_voice_id
        self.room_voice_id = room_voice_id
        self.model_id = model_id
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def voice_for(self, channel: Channel) -> str:
        return self.whisper_voice_id if channel is Channel.WHISPER else self.room_voice_id

    async def synthesize(self, text: str, channel: Channel) -> str | None:
        """Returns base64 mp3, or None if synthesis is unavailable."""
        if not self.enabled or not text:
            return None

        import httpx

        voice_id = self.voice_for(channel)
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                # Whisper lines are urgent and clipped; room lines are measured.
                "stability": 0.35 if channel is Channel.WHISPER else 0.5,
                "similarity_boost": 0.75,
                "speed": 1.12 if channel is Channel.WHISPER else 1.0,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(
                    _TTS_URL.format(voice_id=voice_id),
                    headers={"xi-api-key": self.api_key, "accept": "audio/mpeg"},
                    json=payload,
                )
                resp.raise_for_status()
                return base64.b64encode(resp.content).decode("ascii")
        except Exception as exc:
            log.warning("TTS failed on %s channel: %s", channel.value, exc)
            return None


def whisper_speech(headline: str, detail: str, suggested: str) -> str:
    """What the earpiece actually says - short, because it lands mid-sentence."""
    parts = [headline]
    if detail:
        parts.append(detail)
    if suggested:
        parts.append(f"Try: {suggested}")
    return " ".join(parts)
