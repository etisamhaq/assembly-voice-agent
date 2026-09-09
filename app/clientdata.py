"""Stand-in for the CRM / custodian the agent would really query.

Kept deliberately small and obviously fake. The point of the demo is the voice
pipeline, not a portfolio database - but the room agent needs something real to
answer from, or its replies are vapour.
"""
from __future__ import annotations

CLIENT_RECORD = {
    "household": "Okafor household",
    "primary": {"name": "Dana Okafor", "age": 58, "employment": "Operations director"},
    "secondary": {"name": "Sam Okafor", "age": 61, "employment": "Semi-retired, contract work"},
    "risk_profile": "Moderate (last assessed 14 months ago - due for review)",
    "time_horizon": "7 years to first withdrawal",
    "accounts": [
        {"type": "401(k) - former employer", "balance_usd": 412_000, "note": "Candidate for rollover"},
        {"type": "Roth IRA", "balance_usd": 96_500},
        {"type": "Taxable brokerage", "balance_usd": 148_200},
        {"type": "Cash / emergency reserve", "balance_usd": 21_000, "note": "≈3 months expenses"},
    ],
    "current_allocation": {"equities": 0.72, "fixed_income": 0.21, "cash": 0.05, "alternatives": 0.02},
    "target_allocation": {"equities": 0.60, "fixed_income": 0.33, "cash": 0.05, "alternatives": 0.02},
    "flags": [
        "Equity allocation is 12 points above target - drift since last rebalance.",
        "Risk questionnaire is overdue; suitability file is stale.",
        "Emergency reserve is thin relative to stated horizon.",
    ],
    "last_review": "2025-07-09",
}


def as_prompt_context() -> str:
    lines = [
        f"Household: {CLIENT_RECORD['household']}",
        f"Primary: {CLIENT_RECORD['primary']['name']}, {CLIENT_RECORD['primary']['age']}",
        f"Secondary: {CLIENT_RECORD['secondary']['name']}, {CLIENT_RECORD['secondary']['age']}",
        f"Risk profile: {CLIENT_RECORD['risk_profile']}",
        f"Time horizon: {CLIENT_RECORD['time_horizon']}",
        "Accounts:",
    ]
    for a in CLIENT_RECORD["accounts"]:
        note = f" ({a['note']})" if a.get("note") else ""
        lines.append(f"  - {a['type']}: ${a['balance_usd']:,}{note}")
    cur = CLIENT_RECORD["current_allocation"]
    tgt = CLIENT_RECORD["target_allocation"]
    lines.append(
        "Current allocation: "
        + ", ".join(f"{k} {v:.0%}" for k, v in cur.items())
        + " | Target: "
        + ", ".join(f"{k} {v:.0%}" for k, v in tgt.items())
    )
    lines.append("Flags: " + "; ".join(CLIENT_RECORD["flags"]))
    return "\n".join(lines)
