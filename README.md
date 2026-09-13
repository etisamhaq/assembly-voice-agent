# Second Chair

**The AI that sits in the room with you — and knows when to whisper and when to speak.**

**Website → https://second-chair-chi.vercel.app**

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
| Advisor says *"guaranteed to return eight percent"* | whisper in **0 ms**: *"'Guaranteed' is a FINRA 2210 violation — say 'historically averaged'"* | rule engine |
| Advisor implies a recommendation with no risk disclosure | whisper a beat later | Claude judge |
| Spouse goes quiet for 94 s | whisper: *"Spouse has been silent — bring them in"* | engagement monitor |
| *"Second Chair, what's their allocation?"* | **speaks aloud** to the room | addressivity + Claude |
| 18 of 20 turns | **says nothing at all** | addressivity |
| Call ends | FINRA-clean, PII-free, speaker-attributed audit log | `audit.py` |

Run `python demo.py` to watch exactly this, with no API keys.

---

## Deployment

Two deployments, on purpose:

| What | Where | Why |
|---|---|---|
| The API (`app/`) | Render, one Docker container | Holds session state in memory and keeps a WebSocket open for the length of a call — it needs an always-on container. It serves no pages. |
| Everything a person sees (`site/`) | Vercel, Next.js | The marketing pages *and* the live demo console, which talks to the API over a cross-origin WebSocket |

The site reads the app's `/api/health` cross-origin to tell visitors whether the demo container
is awake before they click, which is why the app sets `SC_CORS_ORIGINS` (default `*`, read-only).

```bash
docker build -t second-chair .
docker run -p 8000:8000 -e GROQ_API_KEY=... -e ASSEMBLYAI_API_KEY=... second-chair
```

The app holds per-session state in memory and keeps a WebSocket open for the length of a call,
so it needs an always-on container — serverless functions will not work. `render.yaml` is a
ready blueprint; the same image runs on Fly.io, Railway, or any container host.

Two things to know about free tiers: the container sleeps when idle (a cold start mid-demo is
worse than it sounds), and there is no persistent disk, so `SC_AUDIT_DIR` points at `/tmp` and
audit logs vanish on restart. Mount a volume and repoint `SC_AUDIT_DIR` to keep them.

HTTPS is not optional — browsers block `getUserMedia` on plain HTTP, so live mic mode simply
will not start without it.

## Quick start

```bash
./run.sh                 # venv, deps, server on http://127.0.0.1:8000
```

Then open the console and press **Start call**. It runs the scripted three-party call with
zero configuration.

```bash
python demo.py                    # same call, in the terminal, instantly
python demo.py --speed 1          # real time, for recording narration
pytest                            # 132 tests, offline
```

Add keys to `.env` to light up the rest:

```bash
ASSEMBLYAI_API_KEY=...   # live microphone input
GROQ_API_KEY=...         # LLM compliance judge + room agent  (free tier is enough)
ELEVENLABS_API_KEY=...   # optional: spoken audio (the browser speaks otherwise)
ANTHROPIC_API_KEY=...    # optional: Claude instead of Groq
```

```bash
python check_llm.py      # what can my keys actually reach?
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

## The LLM layer

Both LLM jobs — the tier-2 compliance judge and the room agent — go through one interface
(`app/llm.py`). Three providers, tried in order; any one is enough.

| Backend | Auth | Notes |
|---|---|---|
| `groq` *(default)* | `GROQ_API_KEY` | fast, capable free tier, full tool-calling |
| `assemblyai-gateway` | `ASSEMBLYAI_API_KEY` | same key as transcription — but Claude there needs a **paid** AssemblyAI account |
| `anthropic` | `ANTHROPIC_API_KEY` | native structured outputs + the `effort` lever |

Groq leads because its free tier actually serves capable models. The AssemblyAI gateway is a
genuinely nice idea — one credential for transcription *and* inference — but an unbilled account
reaches only `qwen3.5-4b-32k-fast`, so it is the fallback rather than the default.

### Why `structured()` walks a ladder

Structured output is the awkward part, because what a provider allows depends on the model *and*
the account:

- Claude on the gateway accepts `tools` + `tool_choice`, but Opus 5 rejects `response_format`.
- Groq's `gpt-oss-*` and `qwen3.8-27b` accept everything; `groq/compound` accepts neither tools
  nor `json_schema`.
- An unbilled gateway account gets `qwen3.5-4b-32k-fast`, which rejects **both**.

So the OpenAI-compatible backend tries a forced tool call, falls back to `json_schema`, and falls
back again to prompt-coerced JSON — dropping a rung whenever the provider says it cannot do that,
and caching the rung that worked so the probe is paid once per process, not once per turn.
Providers phrase the refusal four different ways (`does not support`, `is not supported`,
`unsupported`, `tool_use_failed`); all four drop a rung. Prompt-coerced replies arrive fenced,
prefaced with prose, or trailing commentary — `extract_json()` recovers the object from all three.

### Reasoning models

Groq's `gpt-oss` family spends `max_tokens` on hidden reasoning *before* emitting a visible
character, so a budget sized for the answer returns empty content with `finish_reason="length"`.
The backend floors the token budget, sends `reasoning_effort=low`, drops that parameter
permanently if a model rejects it, and retries once at a larger budget if reasoning ate the whole
allowance. Without this, `gpt-oss-120b` looks like it has no access at all.

### Rate limits

Free tiers throttle. Requests are serialised, spaced (`min_interval_s`), and retried through 429s
honouring `Retry-After`. Tier 2 is best-effort by design, so a throttled turn costs a nuance
finding, never a call: **the deterministic tier needs no LLM** and still catches every pattern
violation in 0 ms.

Replaying at `--speed 0` fires every judge call at once, so tier-2 findings bunch up at the end;
at realistic pace they interleave naturally.

### Measured, not assumed

`check_llm.py` probes every provider you have a key for and reports which models answer, which
structuring rung each lands on, and how fast:

```
model                          chat   structured       ms
openai/gpt-oss-120b            yes    tool_call       235
openai/gpt-oss-20b             yes    tool_call       456
qwen/qwen3.8-27b               yes    tool_call       439
groq/compound                  yes    prompted       1038
```

## AssemblyAI surface used

| Feature | Where |
|---|---|
| Universal-Streaming v3 WebSocket | `app/sources/assemblyai.py` |
| LLM Gateway (optional backend, same key) | `app/llm.py`, `check_llm.py` |
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
  llm.py        LLM interface — groq | gateway | anthropic | none
  factory.py    wiring shared by the server and the demo
  guardrails.py redaction (runs first, always)
  compliance.py rule engine + Claude judge
  addressivity.py  speak or stay silent
  engagement.py    who has gone quiet, and how do they sound
  roomagent.py     what the agent says out loud
  pipeline.py      the orchestrator
  audit.py         append-only, PII-free session record
  main.py          FastAPI + WebSocket
site/           everything with a UI (Next.js) — pages plus the demo console
  app/demo/       the live console route
  components/demo/  session socket, audio channels, console UI
tests/          132 tests
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
| `SC_LLM_BACKEND` | `auto` | order is groq → gateway → anthropic; pin with `groq`, `gateway`, `anthropic`, `off` |
| `SC_GROQ_JUDGE_MODEL` | `openai/gpt-oss-120b` | detached from the budget, so it takes the stronger model |
| `SC_GROQ_ROOM_MODEL` | `openai/gpt-oss-20b` | heard aloud, so it takes the faster one |
| `SC_LLM_REGION` | `us` | `us` or `eu` gateway endpoint |
| `SC_GATEWAY_MODEL` | `qwen3.5-4b-32k-fast` | model used on the gateway — run `check_llm.py` |
| `SC_JUDGE_MODEL` | `claude-opus-5` | anthropic backend only |
| `SC_JUDGE_EFFORT` | `low` | anthropic backend only; raise for harder review |
| `SC_ROOM_MODEL` | `claude-opus-5` | anthropic backend only |
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
- Tier-2 judge quality tracks the model behind it. On Groq's free tier (`gpt-oss-120b`) it
  reliably finds omitted risk disclosures and premature recommendations; on the AssemblyAI free
  tier (a 4B model) it is much weaker. Both are verified end to end.
