"""Runtime configuration, resolved once from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is convenience only
    pass

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT.parent / "web"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    assemblyai_key: str = field(default_factory=lambda: os.getenv("ASSEMBLYAI_API_KEY", ""))
    anthropic_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    elevenlabs_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))

    whisper_voice_id: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_WHISPER_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    )
    room_voice_id: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_ROOM_VOICE_ID", "AZnzlk1XvdvUeBnXmlld")
    )

    judge_model: str = field(default_factory=lambda: os.getenv("SC_JUDGE_MODEL", "claude-opus-5"))
    room_model: str = field(default_factory=lambda: os.getenv("SC_ROOM_MODEL", "claude-opus-5"))
    judge_effort: str = field(default_factory=lambda: os.getenv("SC_JUDGE_EFFORT", "low"))

    source: str = field(default_factory=lambda: os.getenv("SC_SOURCE", "simulated"))
    max_speakers: int = field(default_factory=lambda: _int("SC_MAX_SPEAKERS", 3))
    silence_nudge_seconds: int = field(default_factory=lambda: _int("SC_SILENCE_NUDGE_SECONDS", 90))
    whisper_budget_ms: int = field(default_factory=lambda: _int("SC_WHISPER_LATENCY_BUDGET_MS", 1000))

    sample_rate: int = 16_000
    rules_path: Path = ROOT / "rules" / "finra.yaml"
    audit_dir: Path = ROOT.parent / "audit"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_key)

    @property
    def tts_enabled(self) -> bool:
        return bool(self.elevenlabs_key)

    @property
    def live_audio_enabled(self) -> bool:
        return bool(self.assemblyai_key)


settings = Settings()
