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
    groq_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    assemblyai_key: str = field(default_factory=lambda: os.getenv("ASSEMBLYAI_API_KEY", ""))
    anthropic_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    elevenlabs_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))

    whisper_voice_id: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_WHISPER_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    )
    room_voice_id: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_ROOM_VOICE_ID", "AZnzlk1XvdvUeBnXmlld")
    )

    # "auto" prefers the AssemblyAI LLM Gateway, so one key runs everything.
    llm_backend: str = field(default_factory=lambda: os.getenv("SC_LLM_BACKEND", "auto"))
    llm_region: str = field(default_factory=lambda: os.getenv("SC_LLM_REGION", "us"))

    # Groq (default backend). Separate models per role: the judge is detached
    # so it can afford the stronger model, the room agent is heard aloud so it
    # takes the faster one.
    groq_judge_model: str = field(
        default_factory=lambda: os.getenv("SC_GROQ_JUDGE_MODEL", "openai/gpt-oss-120b")
    )
    groq_room_model: str = field(
        default_factory=lambda: os.getenv("SC_GROQ_ROOM_MODEL", "openai/gpt-oss-20b")
    )

    # Used when the gateway backend is active. The free-tier default is the
    # only model reachable without paid gateway access; set it to
    # claude-opus-5 once the AssemblyAI account has Claude entitlements.
    gateway_model: str = field(
        default_factory=lambda: os.getenv("SC_GATEWAY_MODEL", "qwen3.5-4b-32k-fast")
    )

    judge_model: str = field(default_factory=lambda: os.getenv("SC_JUDGE_MODEL", "claude-opus-5"))
    room_model: str = field(default_factory=lambda: os.getenv("SC_ROOM_MODEL", "claude-opus-5"))
    judge_effort: str = field(default_factory=lambda: os.getenv("SC_JUDGE_EFFORT", "low"))

    # Comma-separated origins allowed to read the public API. The marketing
    # site is served from a different host, so it needs this to read /api/health.
    cors_origins: str = field(default_factory=lambda: os.getenv("SC_CORS_ORIGINS", "*"))

    source: str = field(default_factory=lambda: os.getenv("SC_SOURCE", "simulated"))
    max_speakers: int = field(default_factory=lambda: _int("SC_MAX_SPEAKERS", 3))
    silence_nudge_seconds: int = field(default_factory=lambda: _int("SC_SILENCE_NUDGE_SECONDS", 90))
    whisper_budget_ms: int = field(default_factory=lambda: _int("SC_WHISPER_LATENCY_BUDGET_MS", 1000))

    sample_rate: int = 16_000
    rules_path: Path = ROOT / "rules" / "finra.yaml"
    # Overridable because a container's app directory is usually read-only,
    # and on Render's free plan (no disks) this has to live somewhere ephemeral.
    audit_dir: Path = field(
        default_factory=lambda: Path(os.getenv("SC_AUDIT_DIR", str(ROOT.parent / "audit")))
    )

    @property
    def llm_enabled(self) -> bool:
        """Any one of the three credentials can drive the judge and room agent."""
        keys = {
            "groq": self.groq_key,
            "gateway": self.assemblyai_key,
            "anthropic": self.anthropic_key,
        }
        if self.llm_backend == "off":
            return False
        if self.llm_backend in keys:
            return bool(keys[self.llm_backend])
        return any(keys.values())

    @property
    def tts_enabled(self) -> bool:
        return bool(self.elevenlabs_key)

    @property
    def live_audio_enabled(self) -> bool:
        return bool(self.assemblyai_key)


settings = Settings()
