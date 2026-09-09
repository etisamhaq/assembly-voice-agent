# Second Chair

**The AI that sits in the room with you — and knows when to whisper and when to speak.**

Built for the [AssemblyAI Voice Agent Hackathon](https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon).

---

## The gap

Every voice agent on the market assumes **one human ↔ one agent**. Real high-stakes
conversations are **multi-party**: an advisor, a client, and the client's spouse. A nurse, a
patient, and their daughter. Drop today's agents into that room and they fall apart — they
don't know who is talking, they interrupt constantly, and they answer questions that were
never addressed to them.

Second Chair is built for the room. Its defining property is **two output channels**:

| Channel | Who hears it | What it carries |
|---|---|---|
| **Whisper** | the professional's earpiece, privately | compliance warnings, coaching, the exact words to say next |
| **Room** | everyone, aloud | answers — but **only** when the agent is addressed by name |

Named after the junior attorney who sits beside lead counsel: never runs the meeting, always
has the answer.

---

## What it does, in one call

A financial advisor is on a call with a client and their spouse about a 401(k) rollover.

| Moment | Second Chair | Powered by |
|---|---|---|
| Three people talking | live speaker-attributed transcript | AssemblyAI streaming diarization |
| Client reads out an SSN | redacted before it is stored or sent anywhere | `guardrails.py` |
| Advisor says *"guaranteed to return eight percent"* | 🔴 whisper in **0 ms**: *"'Guaranteed' is a FINRA 2210 violation — say 'historically averaged'"* | rule engine |
| Advisor implies a recommendation with no risk disclosure | ⚠️ whisper a beat later | Claude judge |
| Spouse goes quiet for 94 s | 🟢 whisper: *"Spouse has been silent — bring them in"* | engagement monitor |
| *"Second Chair, what's their allocation?"* | **speaks aloud** to the room | addressivity + Claude |
| 18 of 20 turns | **says nothing at all** | addressivity |
| Call ends | FINRA-clean, PII-free, speaker-attributed audit log | `audit.py` |

Run `python demo.py` to watch exactly this, with no API keys.

---

## Quick start

```bash
./run.sh                 # venv, deps, server on http://127.0.0.1:8000
```

Then open the console and press **Start call**. It runs the scripted three-party call with
zero configuration.

```bash
python demo.py                    # same call, in the terminal, instantly
python demo.py --speed 1          # real time, for recording narration
pytest                            # 93 tests, ~0.3s
```

Add keys to `.env` to light up the rest:

```bash
ASSEMBLYAI_API_KEY=...   # live microphone input
ANTHROPIC_API_KEY=...    # LLM compliance judge + the room agent's answers
ELEVENLABS_API_KEY=...   # spoken whisper/room audio (browser TTS is the fallback)
```

Every capability degrades independently — the system runs, and the test suite passes, with
none of them set.

**Wear headphones for the demo.** Whisper audio is panned hard left, room audio is centred.
The two channels are physically distinguishable, which is the whole premise and the one thing
a screenshot cannot show.

---

## Architecture

```
                  ┌─── AssemblyAI Universal-Streaming v3 (wss) ────┐
  room mic ──────►│  speaker_labels · turn detection · ~150ms p50  │
                  └────────────────────┬──────────────────────────-┘
                                       │  finalized Turn + speaker
                            ┌──────────┴──────────┐
                            ▼                     ▼
                     redaction              compliance
                    (always first)      ┌──────────┴──────────┐
                            │           ▼                     ▼
                            │    rule engine            Claude judge
                            │    (<1ms, sync)        (concurrent, detached)
                            │           │                     │
                            ▼           ▼                     ▼
                      audit log    WHISPER CHANNEL ◄───────────┘
                                   (private, panned left)

                     addressivity ──► ROOM CHANNEL  (aloud, only when addressed)
```

**The ordering is the product.** Redaction runs first because nothing downstream may see raw
PII. The rule engine runs second because the whisper budget is the number that decides whether
the earpiece is worth wearing. The Claude judge is *detached* — correctness that arrives late
is still worth having, but it must never be able to delay a "you just said guaranteed" warning.

### Where the difficulty actually is

**1. Addressivity** (`app/addressivity.py`) — deciding whether an utterance is aimed at the
agent, at another human, or at nobody. A two-party agent never faces this. Second Chair is
deliberately biased toward silence: a missed summons costs one repeat, a false positive costs
the advisor's credibility in front of their client. `"Second Chair, pull up the statement"`
speaks; `"Second Chair is recording this call"` does not.

**2. The two-tier latency split** (`app/compliance.py`) — a regex cannot see an omitted risk
disclosure, and an LLM cannot answer in 200 ms. So both run: deterministic rules meet the
budget, Claude adds what patterns structurally cannot, and neither blocks the other.

**3. Redaction before persistence** (`app/guardrails.py`) — local and deterministic, because a
network round-trip does not fit inside the whisper budget. Handles spoken digit runs
(*"four one two nine nine…"*), Luhn-gates card numbers, and leaves ordinary figures alone —
`"72 percent equities"` must survive untouched or the transcript becomes unreadable.

---

## AssemblyAI surface used

| Feature | Where |
|---|---|
| Universal-Streaming v3 WebSocket | `app/sources/assemblyai.py` |
| `universal-3-5-pro` realtime model | connection params |
| Streaming speaker diarization (`speaker_labels`, `max_speakers`) | per-word labels → dominant-speaker attribution |
| Turn detection (`end_of_turn`, `end_of_turn_confidence`) | only finalized turns reach compliance |
| Formatted turns | `format_turns=true` |

Key detail that is easy to get wrong: the API key goes in the `Authorization` header with
**no** `Bearer` prefix.

---

## Layout

```
app/
  sources/      transcript sources — assemblyai.py (live) | simulated.py (scripted)
  rules/        finra.yaml — the deterministic rule pack
  scripts/      advisory_call.json — the demo call
  guardrails.py redaction (runs first, always)
  compliance.py rule engine + Claude judge
  addressivity.py  speak or stay silent
  engagement.py    who has gone quiet, and how do they sound
  roomagent.py     what the agent says out loud
  pipeline.py      the orchestrator
  audit.py         append-only, PII-free session record
  main.py          FastAPI + WebSocket
web/            the operator console
tests/          93 tests
```

## Testing

```bash
pytest                              # everything
pytest tests/test_addressivity.py   # the silence guarantees
pytest tests/test_pipeline.py       # end-to-end on the scripted call
```

The `SimulatedSource` is not a throwaway mock — it emits the same `Turn` objects the live
AssemblyAI source emits, including interim partials, so every downstream stage runs its real
code path. Timestamps come from the script's own call timeline rather than the wall clock,
so silence thresholds behave identically at 1× and at 40×: the tests run in 0.3 s and the demo
runs in real time, against the same code.

Guarantees the suite enforces:

- a raw SSN never reaches the audit log, the UI, or an LLM prompt
- ordinary numbers are never over-redacted
- correctly-hedged advisor phrasing is never flagged
- the agent stays silent on all 18 non-addressed turns
- the fast path stays inside its budget even with a slow judge attached
- an LLM outage does not break the call

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `SC_JUDGE_MODEL` | `claude-opus-5` | the latency lever — `claude-sonnet-5` / `claude-haiku-4-5` trade accuracy for speed |
| `SC_JUDGE_EFFORT` | `low` | in-model latency control; raise for harder review |
| `SC_ROOM_MODEL` | `claude-opus-5` | answers spoken aloud |
| `SC_SILENCE_NUDGE_SECONDS` | `90` | when a quiet participant earns a nudge |
| `SC_WHISPER_LATENCY_BUDGET_MS` | `1000` | breaching it is counted and surfaced |
| `SC_MAX_SPEAKERS` | `3` | diarization hint |

## Known limits

- The client record (`app/clientdata.py`) is a fixture, not a CRM integration.
- The rule pack is a credible FINRA/SEC starting set, not a compliance product. It is a
  demonstration of the mechanism; a real deployment needs counsel-reviewed rules.
- PII redaction is local and pattern-based. `Redactor` is an interface precisely so a hosted
  redaction backend can be slotted into the audit path, which is not latency-bound.
- Live mode assumes one shared room microphone. Per-speaker channels would give perfect
  separation without diarization.
