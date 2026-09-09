from app.engagement import EngagementMonitor
from app.models import Role, Turn


def t(text, role, at):
    return Turn(text=text, role=role, received_at_ms=at)


def test_silence_nudge_fires_after_threshold():
    m = EngagementMonitor(silence_threshold_s=90)
    m.observe(t("Sounds high to me.", Role.SPOUSE, 45_000))
    m.observe(t("Okay.", Role.CLIENT, 100_000))
    m.observe(t("Right.", Role.ADVISOR, 105_000))

    assert m.check(120_000) == []                       # 75s - not yet
    nudges = m.check(140_000)                            # 95s
    assert len(nudges) == 1
    assert "Spouse" in nudges[0].headline
    assert nudges[0].suggested_phrasing


def test_nudge_does_not_repeat_within_cooldown():
    m = EngagementMonitor(silence_threshold_s=90, renudge_cooldown_s=180)
    m.observe(t("Hi.", Role.SPOUSE, 0))
    m.observe(t("Still here.", Role.CLIENT, 95_000))     # client stays engaged
    assert len(m.check(100_000)) == 1                    # spouse silent 100s
    assert m.check(150_000) == []                        # inside cooldown
    assert len(m.check(300_000)) == 1                    # cooldown expired


def test_only_one_nudge_per_check():
    """Two voices in the earpiece at once is noise, not coaching."""
    m = EngagementMonitor(silence_threshold_s=90)
    m.observe(t("Hi.", Role.SPOUSE, 0))
    m.observe(t("Hi.", Role.CLIENT, 5_000))
    m.observe(t("Anyway.", Role.ADVISOR, 100_000))
    nudges = m.check(120_000)                            # both are >90s silent
    assert len(nudges) == 1
    assert "Spouse" in nudges[0].headline                # quietest longest wins


def test_advisor_is_never_nudged():
    m = EngagementMonitor(silence_threshold_s=10)
    m.observe(t("Hello.", Role.ADVISOR, 0))
    m.observe(t("Hello.", Role.CLIENT, 1000))
    assert all("Advisor" not in n.headline for n in m.check(100_000))


def test_sentiment_direction():
    m = EngagementMonitor()
    assert m.score_sentiment("I'm really worried and nervous about this") < 0
    assert m.score_sentiment("That's great, makes sense, I'm comfortable") > 0
    assert m.score_sentiment("The meeting is on Tuesday") == 0


def test_airtime_sums_to_one():
    m = EngagementMonitor()
    m.observe(t("one two three four", Role.ADVISOR, 0))
    m.observe(t("five six", Role.CLIENT, 1000))
    a = m.airtime()
    assert abs(sum(a.values()) - 1.0) < 0.01
    assert a["advisor"] > a["client"]
