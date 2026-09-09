"""Redaction must be aggressive on PII and quiet on ordinary numbers."""
import pytest

from app.guardrails import LocalRedactor

r = LocalRedactor()


@pytest.mark.parametrize(
    "text,kind",
    [
        ("My social is 123-45-6789.", "ssn"),
        ("SSN 123 45 6789 please", "ssn"),
        ("it is four one two nine nine eight seven six five four", "ssn"),
        ("card 4532 0151 1283 0366", "credit_card"),
        ("reach me at jane.doe@example.com", "email"),
        ("call (415) 555-0198", "phone"),
        ("call 415-555-0198", "phone"),
        ("born March 14, 1962", "dob"),
        ("dob 03/14/1962", "dob"),
        ("the account number is 88991234567", "account"),
    ],
)
def test_pii_is_redacted(text, kind):
    out, reds = r.redact(text)
    assert kind in {x.kind for x in reds}, f"{kind} not detected in {text!r}"
    assert "REDACTED" in out


def test_paren_phone_is_fully_consumed():
    out, _ = r.redact("call (415) 555-0198 now")
    assert "(" not in out and "415" not in out


def test_account_keeps_carrier_phrase():
    out, _ = r.redact("The account number is 88991234567")
    assert out.startswith("The account number is")
    assert "88991234567" not in out


@pytest.mark.parametrize(
    "text",
    [
        "We should target 8 percent over 10 years.",
        "I have about 250000 in the 401k.",
        "Let's meet at 3pm on the 14th.",
        "The expense ratio is 0.04 percent.",
        "Their allocation is 72 percent equities.",
    ],
)
def test_ordinary_numbers_survive(text):
    out, reds = r.redact(text)
    assert out == text, f"over-redacted: {out!r}"
    assert reds == []


def test_luhn_gate_rejects_non_card_digit_runs():
    # 16 digits that fail Luhn should not be called a card.
    out, reds = r.redact("reference 1234567812345678")
    assert "credit_card" not in {x.kind for x in reds}


def test_empty_and_idempotent():
    assert r.redact("") == ("", [])
    once, _ = r.redact("ssn 123-45-6789")
    twice, _ = r.redact(once)
    assert once == twice
