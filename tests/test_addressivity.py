"""Silence is the default. These tests exist to keep it that way."""
import pytest

from app.addressivity import AddressivityDetector
from app.models import Role, Turn


def turn(text, role=Role.ADVISOR, at=10_000):
    return Turn(text=text, role=role, received_at_ms=at)


@pytest.mark.parametrize(
    "text",
    [
        "Second Chair, what is their current allocation?",
        "Second Chair pull up the 2019 statement.",
        "Hey chair, check their risk profile.",
        "What do you think, Second Chair?",
        "Second Chair can you confirm the balance?",
    ],
)
def test_direct_address_is_heard(text):
    assert AddressivityDetector().evaluate(turn(text)).addressed


@pytest.mark.parametrize(
    "text",
    [
        "So I think we should rebalance toward bonds.",
        "What happens if the market drops?",
        "Can you read me your social?",
        "How fast do we need to move on this?",
        "That's a good question, let me pull it up.",
    ],
)
def test_human_conversation_is_ignored(text):
    """The failure mode that kills the product: answering people's own talk."""
    assert not AddressivityDetector().evaluate(turn(text)).addressed


@pytest.mark.parametrize(
    "text",
    [
        "Second Chair is recording this call for compliance.",
        "Second Chair will log all of this automatically.",
        "Second Chair's transcript goes into the file.",
    ],
)
def test_third_person_mention_is_not_a_summons(text):
    a = AddressivityDetector().evaluate(turn(text))
    assert not a.addressed
    assert "descriptively" in a.reason


def test_clients_cannot_command_the_agent():
    a = AddressivityDetector().evaluate(
        turn("Second Chair, what's our balance?", role=Role.CLIENT)
    )
    assert not a.addressed


def test_query_strips_the_vocative():
    a = AddressivityDetector().evaluate(turn("Second Chair, what is their allocation?"))
    assert a.query == "what is their allocation?"


def test_followup_window_opens_only_after_the_agent_speaks():
    d = AddressivityDetector(followup_window_s=12)
    t = turn("And what about the Roth?", at=50_000)
    assert not d.evaluate(t).addressed        # agent has not spoken

    d.note_agent_spoke(45_000)
    assert d.evaluate(t).addressed            # 5s later, a question

    d.note_agent_spoke(10_000)                # 40s ago - window closed
    assert not d.evaluate(t).addressed


def test_followup_requires_a_question():
    d = AddressivityDetector(followup_window_s=12)
    d.note_agent_spoke(45_000)
    assert not d.evaluate(turn("Right, that makes sense.", at=50_000)).addressed


def test_empty_turn():
    assert not AddressivityDetector().evaluate(turn("   ")).addressed
