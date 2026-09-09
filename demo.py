#!/usr/bin/env python3
"""Terminal replay of the scripted call - no browser, no keys required.

    python demo.py            # instant
    python demo.py --speed 1  # real time, for recording narration
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.compliance import ComplianceEngine, RuleEngine
from app.config import settings
from app.engagement import EngagementMonitor
from app.factory import build_judge, build_room_agent
from app.pipeline import Pipeline
from app.sources.simulated import SimulatedSource

C = {
    "reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m",
    "advisor": "\033[38;5;141m", "client": "\033[38;5;80m", "spouse": "\033[38;5;211m",
    "critical": "\033[38;5;203m", "warning": "\033[38;5;215m",
    "coach": "\033[38;5;79m", "room": "\033[38;5;111m",
}
NAMES = {"advisor": "MARCUS  ", "client": "DANA    ", "spouse": "SAM     ", "unknown": "?       "}


def rule(ch="─", width=96):
    print(C["dim"] + ch * width + C["reset"])


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=0.0, help="0 = instant, 1 = real time")
    args = ap.parse_args()

    async def emit(ev):
        t = ev["type"]
        if t == "turn.processed":
            turn = ev["turn"]
            col = C.get(turn["role"], "")
            secs = turn["start_ms"] // 1000
            clock = f"{secs // 60:02d}:{secs % 60:02d}"
            tags = ""
            if ev["redactions"]:
                tags += C["room"] + f"  [{','.join(r['kind'] for r in ev['redactions'])} redacted]" + C["reset"]
            if ev["addressed_to_agent"]:
                tags += C["room"] + "  [addressed agent]" + C["reset"]
            print(f'{C["dim"]}{clock}{C["reset"]} {col}{NAMES[turn["role"]]}{C["reset"]} {turn["text"]}{tags}')
        elif t == "whisper":
            col = C.get(ev["severity"], "")
            mark = "██" if ev["severity"] == "critical" else "▓▓" if ev["severity"] == "warning" else "░░"
            print(f'      {col}{mark} EARPIECE  {C["bold"]}{ev["headline"]}{C["reset"]}'
                  f'{C["dim"]}  ({ev["latency_ms"]}ms · {ev["rule_id"]}){C["reset"]}')
            if ev["detail"]:
                print(f'         {C["dim"]}{ev["detail"]}{C["reset"]}')
            if ev["suggested_phrasing"]:
                print(f'         {col}say ▸{C["reset"]} {ev["suggested_phrasing"]}')
        elif t == "room":
            print(f'      {C["room"]}◆◆ ALOUD     {C["bold"]}{ev["text"]}{C["reset"]}'
                  f'{C["dim"]}  ({ev["latency_ms"]}ms){C["reset"]}')

    src = SimulatedSource(speed=args.speed)
    pipeline = Pipeline(
        compliance=ComplianceEngine(RuleEngine.from_path(settings.rules_path), build_judge()),
        room_agent=build_room_agent(),
        emit=emit,
        engagement=EngagementMonitor(silence_threshold_s=settings.silence_nudge_seconds),
        whisper_budget_ms=settings.whisper_budget_ms,
    )

    rule("━")
    print(f'  {C["bold"]}SECOND CHAIR{C["reset"]}  {C["dim"]}·  {src.title}{C["reset"]}')
    caps = []
    caps.append(("LLM judge", pipeline.compliance.judge.enabled))
    caps.append(("room agent", pipeline.room_agent.enabled))
    backend = pipeline.compliance.judge.backend
    print("  " + C["dim"] + "  ".join(
        f'{"✓" if on else "○"} {n}' for n, on in caps
    ) + f'   {len(pipeline.compliance.rules.rules)} rules loaded'
        + (f'   via {backend.name} ({backend.model})' if backend.enabled else '')
        + C["reset"])
    rule("━")

    summary = await pipeline.run(src)

    rule("━")
    sev = summary["violations_by_severity"]
    print(f'  {C["bold"]}{summary["turns"]}{C["reset"]} turns   '
          f'{C["critical"]}{sev.get("critical", 0)} critical{C["reset"]}   '
          f'{C["warning"]}{sev.get("warning", 0)} warning{C["reset"]}   '
          f'{C["coach"]}{sev.get("coach", 0)} coaching{C["reset"]}   '
          f'{summary["redactions"]} PII redacted   '
          f'{summary["room_replies"]} spoken aloud')
    air = summary["airtime"]
    print(f'  {C["dim"]}airtime{C["reset"]}  ' + "   ".join(
        f'{C.get(k, "")}{k} {v:.0%}{C["reset"]}' for k, v in air.items()))
    print(f'  {C["dim"]}worst fast-path latency: {summary["max_fast_path_ms"]}ms '
          f'(budget {pipeline.whisper_budget_ms}ms, {summary["budget_misses"]} misses){C["reset"]}')
    rule("━")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
