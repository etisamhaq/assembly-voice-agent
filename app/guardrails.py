"""Real-time PII redaction.

Everything downstream of this module - the audit log, the LLM judge prompt, the
UI transcript - sees redacted text only. Raw text never leaves `Pipeline`.

Redaction runs on the fast path, so it is deterministic and local: a network
round-trip inside a <1s whisper budget is not affordable. `Redactor` is an
interface so a hosted redaction backend can be swapped in for the audit-log
path (which is not latency-bound) without touching the pipeline.
"""
from __future__ import annotations

import re
from typing import Protocol

from .models import Redaction

# Spoken numbers arrive from STT as digits, words, or a mix ("four one two...").
_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3",
    "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}

_SPOKEN_RUN = re.compile(
    r"\b(?:(?:%s)[\s,-]+){4,}(?:%s)\b" % ("|".join(_DIGIT_WORDS), "|".join(_DIGIT_WORDS)),
    re.IGNORECASE,
)

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # SSN: 123-45-6789, 123 45 6789, 123456789
    ("ssn", re.compile(r"(?<!\d)\d{3}[-.\s]?\d{2}[-.\s]?\d{4}(?!\d)"), "[SSN_REDACTED]"),
    # Card: 13-19 digits in groups, Luhn-checked below
    ("credit_card", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"), "[CARD_REDACTED]"),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"), "[EMAIL_REDACTED]"),
    # Lookarounds, not \b, so a leading "(" in "(415) 555-0198" is consumed.
    (
        "phone",
        re.compile(r"(?<![\w])(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"),
        "[PHONE_REDACTED]",
    ),
    (
        "dob",
        re.compile(
            r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b"
            r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?:19|20)\d{2}\b",
            re.IGNORECASE,
        ),
        "[DOB_REDACTED]",
    ),
    # Only the digits are replaced (named group `num`), so the carrier phrase
    # "the account number is ..." survives for the audit reader.
    (
        "account",
        re.compile(
            r"\b(?:account|acct\.?|routing)\b(?:\s+(?:number|numbers|#|no\.?|is|are|was|ending|in|the))*"
            r"\s*:?\s*(?P<num>\d{6,})\b",
            re.IGNORECASE,
        ),
        "[ACCOUNT_REDACTED]",
    ),
]

# Applied first so a spoken-digit SSN is caught before the numeric patterns run.
_ORDER = ["ssn", "credit_card", "account", "dob", "phone", "email"]


def _luhn(digits: str) -> bool:
    """Card numbers validate; a 16-digit account reference usually does not."""
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class Redactor(Protocol):
    def redact(self, text: str) -> tuple[str, list[Redaction]]: ...


class LocalRedactor:
    """Deterministic, sub-millisecond redaction suitable for the fast path."""

    def __init__(self, *, redact_spoken_digits: bool = True) -> None:
        self.redact_spoken_digits = redact_spoken_digits

    def redact(self, text: str) -> tuple[str, list[Redaction]]:
        if not text:
            return text, []

        found: dict[str, int] = {}
        out = text

        if self.redact_spoken_digits:
            def _spoken(m: re.Match[str]) -> str:
                found["ssn"] = found.get("ssn", 0) + 1
                return "[SSN_REDACTED]"

            out = _SPOKEN_RUN.sub(_spoken, out)

        by_kind = {kind: (pat, ph) for kind, pat, ph in _PATTERNS}
        for kind in _ORDER:
            pattern, placeholder = by_kind[kind]

            def _sub(m: re.Match[str], _k: str = kind, _p: str = placeholder) -> str:
                raw = m.group(0)
                digits = re.sub(r"\D", "", raw)
                # A 13-19 digit run is only a card if it passes Luhn; otherwise
                # leave it for a later, more specific pattern or as plain text.
                if _k == "credit_card" and not (13 <= len(digits) <= 19 and _luhn(digits)):
                    return raw
                found[_k] = found.get(_k, 0) + 1
                if "num" in (m.re.groupindex or {}):
                    # Replace only the sensitive digits, keep the carrier phrase.
                    start, end = m.span("num")
                    return raw[: start - m.start()] + _p + raw[end - m.start() :]
                return _p

            out = pattern.sub(_sub, out)

        redactions = [
            Redaction(kind=k, placeholder=by_kind[k][1] if k in by_kind else "[REDACTED]", count=c)
            for k, c in found.items()
        ]
        return out, redactions


class NullRedactor:
    """For tests that need to assert on raw text."""

    def redact(self, text: str) -> tuple[str, list[Redaction]]:
        return text, []
