"""Wiring helpers shared by the server and the terminal demo.

Each provider gets its own model settings, because "the best model" is not the
same string across providers - and the judge and the room agent want different
tradeoffs from the same provider: the judge is detached and can afford the
stronger model, the room agent is heard aloud and needs the faster one.
"""
from __future__ import annotations

from .compliance import LLMJudge
from .config import Settings, settings as default_settings
from .llm import build_backend
from .roomagent import RoomAgent


def _backend(role: str, cfg: Settings):
    judging = role == "judge"
    return build_backend(
        groq_key=cfg.groq_key,
        assemblyai_key=cfg.assemblyai_key,
        anthropic_key=cfg.anthropic_key,
        groq_model=cfg.groq_judge_model if judging else cfg.groq_room_model,
        gateway_model=cfg.gateway_model,
        model=cfg.judge_model if judging else cfg.room_model,
        prefer=cfg.llm_backend,
        region=cfg.llm_region,
        effort=cfg.judge_effort,
    )


def build_judge(cfg: Settings | None = None) -> LLMJudge:
    cfg = cfg or default_settings
    return LLMJudge(_backend("judge", cfg))


def build_room_agent(cfg: Settings | None = None) -> RoomAgent:
    cfg = cfg or default_settings
    return RoomAgent(_backend("room", cfg))
