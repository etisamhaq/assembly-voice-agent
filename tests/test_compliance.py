"""The rule engine is the latency-critical tier - it must be right and fast."""
import time

import pytest

from app.models import Role, Severity

CRITICAL = [
    "This fund is guaranteed to return eight percent a year.",
    "Markets move but this one you cannot lose on.",
    "It's risk-free, basically.",
    "A buddy of mine at the company told me before it's announced.",
    "Let's keep this between us, it's my own fund.",
]

WARNINGS = [
    "There are no fees on the rollover itself.",
    "A direct rollover is completely tax-free.",
    "You need to decide today, the window closes tonight.",
    "It's the best investment available anywhere.",
]

CLEAN = [
    "Historically this has averaged about seven percent, though returns vary.",
    "There's no upfront commission; the expense ratio is 0.4 percent.",
    "Generally it's tax-deferred, but please confirm with your CPA.",
    "Take the week and think it over - I can hold these numbers.",
    "Let me walk you through how the allocation would change.",
    "So what would the monthly contribution look like?",
]


@pytest.mark.parametrize("text", CRITICAL)
def test_critical_violations_fire(rules, text):
    v = rules.scan(text, Role.ADVISOR)
    assert v, f"missed: {text!r}"
    assert v[0].severity is Severity.CRITICAL


@pytest.mark.parametrize("text", WARNINGS)
def test_warnings_fire(rules, text):
    v = rules.scan(text, Role.ADVISOR)
    assert v, f"missed: {text!r}"
    assert v[0].severity in (Severity.WARNING, Severity.CRITICAL)


@pytest.mark.parametrize("text", CLEAN)
def test_compliant_phrasing_is_not_flagged(rules, text):
    assert rules.scan(text, Role.ADVISOR) == [], f"false positive on {text!r}"


def test_client_distress_is_client_scoped(rules):
    text = "I was laid off and I can't afford much right now."
    assert rules.scan(text, Role.CLIENT), "distress cue missed on client"
    # The same words from the advisor are not a client-distress signal.
    assert not [v for v in rules.scan(text, Role.ADVISOR) if v.rule_id == "client-distress"]


def test_advisor_rules_do_not_fire_on_clients(rules):
    assert rules.scan("Is it guaranteed to return 8 percent?", Role.CLIENT) == []


def test_severity_ordering(rules):
    text = "There are no fees and it's guaranteed to return 8 percent."
    v = rules.scan(text, Role.ADVISOR)
    assert len(v) >= 2
    assert v[0].severity is Severity.CRITICAL


def test_every_rule_carries_actionable_guidance(rules):
    for rule in rules.rules:
        assert rule.regulation, f"{rule.id} has no regulation citation"
        assert rule.suggested_phrasing, f"{rule.id} has no suggested phrasing"
        assert len(rule.detail.split()) <= 30, f"{rule.id} detail too long to hear"


def test_fast_path_is_actually_fast(engine):
    """The whole premise is a sub-second whisper. Budget the scan at <15ms."""
    text = "This is guaranteed to return 8 percent and there are no fees at all."
    engine.fast_scan(text, Role.ADVISOR)  # warm
    t0 = time.perf_counter()
    for _ in range(200):
        engine.fast_scan(text, Role.ADVISOR)
    per_call_ms = (time.perf_counter() - t0) / 200 * 1000
    assert per_call_ms < 15, f"{per_call_ms:.2f}ms per scan is too slow"


def test_llm_judge_disabled_without_key(engine):
    assert engine.judge.enabled is False
