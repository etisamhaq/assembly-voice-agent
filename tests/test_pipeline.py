"""End-to-end behaviour of the orchestrator on the scripted call."""
import asyncio
import json

import pytest

from app.audit import AuditLog
from app.compliance import ComplianceEngine, LLMJudge
from app.engagement import EngagementMonitor
from app.models import Role, Severity, Turn, Violation
from app.pipeline import Pipeline
from app.roomagent import RoomAgent
from app.sources.simulated import SimulatedSource


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)

    def of(self, kind):
        return [e for e in self.events if e["type"] == kind]


def build(engine, emit, **kw):
    return Pipeline(
        compliance=engine,
        room_agent=kw.pop("room_agent", RoomAgent()),
        emit=emit,
        engagement=kw.pop("engagement", EngagementMonitor(silence_threshold_s=90)),
        **kw,
    )


@pytest.fixture
async def run(engine):
    rec = Recorder()
    p = build(engine, rec)
    summary = await p.run(SimulatedSource(speed=0))
    return p, rec, summary


async def test_scripted_call_hits_every_beat(run):
    _, rec, summary = run
    assert summary["turns"] == 20
    assert summary["violations_by_severity"]["critical"] == 2
    assert summary["violations_by_severity"]["warning"] >= 3
    assert summary["redactions"] == 1
    assert summary["room_replies"] == 2


async def test_whispers_carry_actionable_phrasing(run):
    _, rec, _ = run
    whispers = rec.of("whisper")
    assert whispers
    for w in whispers:
        assert w["headline"]
        assert w["suggested_phrasing"], f"{w['rule_id']} gave no phrasing to say"


async def test_fast_path_stays_inside_the_budget(run):
    p, rec, summary = run
    assert summary["budget_misses"] == 0
    for w in rec.of("whisper"):
        if w["rule_id"] != "engagement-silence":
            assert w["latency_ms"] <= p.whisper_budget_ms


async def test_ssn_never_leaves_the_pipeline(run):
    _, rec, _ = run
    blob = json.dumps(rec.events)
    assert "412-99-8765" not in blob
    assert "SSN_REDACTED" in blob


async def test_agent_speaks_only_when_addressed(run):
    _, rec, _ = run
    addressed = [e for e in rec.of("turn.processed") if e["addressed_to_agent"]]
    assert len(addressed) == 2
    for e in addressed:
        assert "second chair" in e["turn"]["text"].lower()
    # 18 of 20 turns produced no spoken output at all.
    assert len(rec.of("room")) == 2


async def test_spouse_disengagement_is_caught(run):
    _, rec, summary = run
    nudges = [w for w in rec.of("whisper") if w["rule_id"] == "engagement-silence"]
    assert len(nudges) == 1
    assert "Spouse" in nudges[0]["headline"]
    assert summary["airtime"]["spouse"] < 0.1


async def test_partials_never_reach_compliance(engine):
    rec = Recorder()
    p = build(engine, rec)
    await p.handle_turn(
        Turn(text="This is guaranteed to return 8 percent.", role=Role.ADVISOR, end_of_turn=False)
    )
    assert rec.of("whisper") == []
    assert rec.of("transcript.partial")
    assert p.stats["turns"] == 0


async def test_partials_are_redacted_too(engine):
    rec = Recorder()
    p = build(engine, rec)
    await p.handle_turn(Turn(text="it is 123-45-6789", role=Role.CLIENT, end_of_turn=False))
    assert "123-45-6789" not in json.dumps(rec.events)


async def test_audit_log_is_redacted_and_complete(engine, tmp_path):
    rec = Recorder()
    audit = AuditLog(tmp_path, "testsess")
    p = build(engine, rec, audit=audit)
    summary = await p.run(SimulatedSource(speed=0))
    audit.close(summary)

    raw = audit.path.read_text()
    assert "412-99-8765" not in raw
    assert "SSN_REDACTED" in raw

    lines = [json.loads(x) for x in raw.strip().splitlines()]
    kinds = [x["event"] for x in lines]
    assert kinds[0] == "session.start" and kinds[-1] == "session.end"
    assert kinds.count("turn") == 20
    assert "whisper" in kinds and "room_reply" in kinds
    # Every turn is attributed.
    for line in lines:
        if line["event"] == "turn":
            assert line["role"] in {"advisor", "client", "spouse"}


class StubJudge(LLMJudge):
    """Tier 2 stand-in: finds one thing the regexes structurally cannot."""

    def __init__(self, delay=0.0):
        super().__init__()
        self._client = object()      # marks it enabled
        self.delay = delay
        self.calls = 0

    async def review(self, turn, text, history, already_caught):
        self.calls += 1
        await asyncio.sleep(self.delay)
        if "rollover target" not in text:
            return []
        return [
            Violation(
                rule_id="omitted-risk-disclosure",
                title="Recommendation made without risk disclosure",
                severity=Severity.WARNING,
                regulation="FINRA Rule 2111",
                detail="No downside was mentioned alongside the projection.",
                suggested_phrasing="I should add that this can lose value in a down year.",
                source="llm",
                quote=text[:30],
            )
        ]


async def test_llm_escalation_adds_findings_without_blocking(rules):
    rec = Recorder()
    judge = StubJudge(delay=0.05)
    p = build(ComplianceEngine(rules, judge), rec)
    summary = await p.run(SimulatedSource(speed=0))

    assert judge.calls > 0
    llm_whispers = [w for w in rec.of("whisper") if w["rule_id"] == "omitted-risk-disclosure"]
    assert len(llm_whispers) == 1
    # The fast path still met its budget despite the 50ms judge.
    assert summary["max_fast_path_ms"] < 100


async def test_judge_is_not_called_for_clients(rules):
    rec = Recorder()
    judge = StubJudge()
    p = build(ComplianceEngine(rules, judge), rec)
    await p.handle_turn(Turn(text="I am worried about this.", role=Role.CLIENT))
    assert judge.calls == 0


async def test_judge_failure_does_not_break_the_call(rules):
    class Exploding(StubJudge):
        async def review(self, *a, **kw):
            raise RuntimeError("api down")

    rec = Recorder()
    p = build(ComplianceEngine(rules, Exploding()), rec)
    summary = await p.run(SimulatedSource(speed=0))
    assert summary["turns"] == 20          # call completed anyway
