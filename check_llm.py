#!/usr/bin/env python3
"""What can my keys actually do?

Providers advertise model lists; entitlements and per-model capabilities are a
different question. This probes whichever providers you have keys for, reports
which models answer, which structuring mechanism each lands on, and how fast
they are - then prints the env lines to use.

    python check_llm.py                      # every provider you have a key for
    python check_llm.py --provider groq      # just one
    python check_llm.py --all                # every model, not just the shortlist
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.llm import (
    DEFAULT_GATEWAY_MODEL,
    DEFAULT_GROQ_MODEL,
    GATEWAY_URLS,
    GatewayBackend,
    GroqBackend,
)

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "why": {"type": "string"}},
    "required": ["ok", "why"],
    "additionalProperties": False,
}
DIM, OK, BAD, WARN, RESET, BOLD = (
    "\033[2m", "\033[38;5;79m", "\033[38;5;203m", "\033[38;5;215m", "\033[0m", "\033[1m",
)

# Chat models worth probing by default; the rest are ASR/guard/TTS models.
GROQ_SHORTLIST = [
    "openai/gpt-oss-120b", "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b", "qwen/qwen3.6-27b", "groq/compound",
]


def make(provider: str, model: str):
    if provider == "groq":
        return GroqBackend(settings.groq_key, model=model, min_interval_s=0.0)
    return GatewayBackend(settings.assemblyai_key, model=model, region=settings.llm_region)


async def probe(provider: str, model: str):
    b = make(provider, model)
    t0 = time.perf_counter()
    reply = await b.complete(system="Reply with one word.", user="Say: ok", max_tokens=16)
    ms = int((time.perf_counter() - t0) * 1000)
    if not reply.text:
        return model, False, "-", 0, "no access or empty response"
    data = await b.structured(
        system="You are a checker.", user="Is 2+2=4? Report it.",
        schema=SCHEMA, tool_name="report", max_tokens=400,
    )
    note = "ok" if data else "chat only, no structured output"
    return model, True, b.strategy or "none", ms, note


async def list_models(provider: str) -> list[str]:
    from openai import AsyncOpenAI

    if provider == "groq":
        url, key = GroqBackend.base_url, settings.groq_key
    else:
        url, key = GATEWAY_URLS.get(settings.llm_region, GATEWAY_URLS["us"]), settings.assemblyai_key
    client = AsyncOpenAI(base_url=url, api_key=key, timeout=30)
    return sorted(m.id for m in (await client.models.list()).data)


async def run_provider(provider: str, probe_all: bool) -> tuple[str, list[tuple[str, str, int]]]:
    label = {"groq": "Groq Cloud", "gateway": "AssemblyAI LLM Gateway"}[provider]
    print(f"{BOLD}{label}{RESET}")
    try:
        listed = await list_models(provider)
    except Exception as exc:
        print(f"  {BAD}could not list models: {str(exc)[:90]}{RESET}\n")
        return provider, []
    print(f"{DIM}  lists {len(listed)} models{RESET}")

    if probe_all:
        targets = listed
    elif provider == "groq":
        targets = [m for m in GROQ_SHORTLIST if m in listed] or listed[:5]
    else:
        targets = [m for m in listed if m.startswith("claude")] + [DEFAULT_GATEWAY_MODEL]

    print(f"  {'model':30} {'chat':6} {'structured':12} {'ms':>6}  note")
    print(DIM + "  " + "-" * 80 + RESET)
    usable = []
    for model in targets:
        name, chat, strategy, ms, note = await probe(provider, model)
        if chat:
            usable.append((name, strategy, ms))
            colour = OK if strategy != "none" else WARN
            print(f"  {name:30} {OK}{'yes':6}{RESET} {colour}{strategy:12}{RESET} {ms:>6}  {DIM}{note}{RESET}")
        else:
            print(f"  {name:30} {BAD}{'no':6}{RESET} {DIM}{'-':12} {'':>6}  {note}{RESET}")
        await asyncio.sleep(0.3)
    print()
    return provider, usable


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["groq", "gateway"], action="append")
    ap.add_argument("--all", action="store_true", help="probe every listed model")
    args = ap.parse_args()

    available = []
    if settings.groq_key:
        available.append("groq")
    if settings.assemblyai_key:
        available.append("gateway")
    targets = [p for p in (args.provider or available) if p in available]

    if not targets:
        print(f"{BAD}No provider keys set.{RESET}  Add GROQ_API_KEY or ASSEMBLYAI_API_KEY to .env.")
        print(f"{DIM}Second Chair still runs - the deterministic rule tier needs no LLM.{RESET}")
        return 1

    results = {}
    for provider in targets:
        name, usable = await run_provider(provider, args.all)
        results[name] = usable

    print(f"{BOLD}Recommended configuration{RESET}")
    groq = results.get("groq") or []
    structured = [(m, s, ms) for m, s, ms in groq if s != "none"]
    if structured:
        best = max(structured, key=lambda r: ("120b" in r[0], "gpt-oss" in r[0]))
        fastest = min(structured, key=lambda r: r[2])
        print(f"  SC_LLM_BACKEND=groq")
        print(f"  SC_GROQ_JUDGE_MODEL={best[0]}      {DIM}# strongest, {best[2]}ms{RESET}")
        print(f"  SC_GROQ_ROOM_MODEL={fastest[0]}    {DIM}# fastest, {fastest[2]}ms{RESET}")
        return 0

    gw = [(m, s, ms) for m, s, ms in results.get("gateway", []) if s != "none"]
    if gw:
        print(f"  SC_LLM_BACKEND=gateway")
        print(f"  SC_GATEWAY_MODEL={gw[0][0]}")
        if not any(m.startswith("claude") for m, _, _ in gw):
            print(f"{DIM}  No Claude model is entitled on this AssemblyAI account. Enable paid\n"
                  f"  gateway access to unlock them, or use Groq.{RESET}")
        return 0

    print(f"  {BAD}No model reached structured output. Tier 2 will stay off; the\n"
          f"  deterministic rule tier still runs.{RESET}")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
