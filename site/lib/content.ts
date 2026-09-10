export const DEMO_URL = "https://second-chair-toe5.onrender.com";
export const REPO_URL = "https://github.com/etisamhaq/assembly-voice-agent";

export const nav = [
  { href: "/features", label: "Features" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/use-cases", label: "Use cases" },
  { href: "/faq", label: "FAQ" },
  { href: "/about", label: "About" },
];

/* --------------------------------------------------------------- hero demo */

export type Turn = {
  role: "advisor" | "client" | "spouse" | "agent";
  who: string;
  text: string;
  flag?: string;
  redact?: string;
  whisper?: { sev: "critical" | "warning" | "coach"; rule: string; ms: string; head: string; say: string };
};

export const transcript: Turn[] = [
  {
    role: "advisor",
    who: "Marcus, advisor",
    text: "So the rollover target I'd put you in is guaranteed to return eight percent a year.",
    flag: "guaranteed to return eight percent",
    whisper: {
      sev: "critical",
      rule: "FINRA Rule 2210(d)(1)(B)",
      ms: "0 ms",
      head: "“Guaranteed” return claim",
      say: "Historically this has averaged around eight percent, though past performance doesn't predict future results.",
    },
  },
  { role: "spouse", who: "Sam, spouse", text: "Eight percent guaranteed? What happens if the market drops?" },
  { role: "client", who: "Dana, client", text: "And what does it cost us to move it?" },
  {
    role: "advisor",
    who: "Marcus, advisor",
    text: "There are no fees on the rollover itself.",
    flag: "no fees",
    whisper: {
      sev: "warning",
      rule: "FINRA Rule 2210(d)(1)",
      ms: "0 ms",
      head: "“No fees” claim",
      say: "There's no upfront commission — the expense ratio is 0.4%, and I can walk you through the full cost.",
    },
  },
  { role: "client", who: "Dana, client", text: "My social is 412-99-8765.", redact: "412-99-8765" },
  { role: "advisor", who: "Marcus, advisor", text: "Second Chair, what's their current allocation?" },
  {
    role: "agent",
    who: "Second Chair, aloud",
    text: "Equities seventy-two percent, fixed income twenty-one, cash five, alternatives two.",
  },
];

/* ------------------------------------------------------------------ figures */

export const figures = [
  { label: "Rule-tier warning latency", value: "0", unit: "ms measured" },
  { label: "Turns where the agent stays silent", value: "18", unit: "of 20" },
  { label: "Speakers separated in real time", value: "10", unit: "maximum" },
  { label: "Regulatory rules in the starter pack", value: "9", unit: "FINRA and SEC" },
];

/* ----------------------------------------------------------------- features */

export const features = [
  {
    title: "Two output channels",
    body: "One private line into the professional's earpiece, one spoken into the room. The client never hears a correction; the room only hears the agent when someone addresses it by name.",
    cite: "The distinction is audible — whisper audio is panned hard left, room audio centred.",
  },
  {
    title: "Real-time speaker separation",
    body: "Streaming diarization attributes every word to a speaker as the conversation happens, up to ten voices. Roles are seated automatically and can be reassigned mid-call.",
    cite: "AssemblyAI Universal-Streaming, per-word speaker labels.",
  },
  {
    title: "Deterministic compliance rules",
    body: "A pattern engine scans each finalised turn against a FINRA and SEC rule pack and fires a warning in under a millisecond. It never waits on a network call, so it never misses the moment.",
    cite: "Measured at 0 ms across a full 20-turn call.",
  },
  {
    title: "A second pass that reads context",
    body: "A language model reviews the same turn against the conversation so far and reports what a pattern cannot see: an omitted risk disclosure, a recommendation made before suitability was established, a promise implied across two sentences.",
    cite: "Runs detached, so a slow review can never delay an urgent warning.",
  },
  {
    title: "PII redacted before it lands anywhere",
    body: "Account numbers, dates of birth and social security numbers — including ones read aloud digit by digit — are removed before the transcript is stored, displayed, or sent to a model. Ordinary figures are left intact.",
    cite: "Card numbers are Luhn-checked so reference numbers aren't wrongly redacted.",
  },
  {
    title: "Knows when it isn't being spoken to",
    body: "Most of what the agent hears is two people talking to each other. It answers only a direct address, and treats being mentioned in the third person as conversation, not a summons.",
    cite: "Biased toward silence: a missed cue costs one repeat, a false answer costs credibility.",
  },
  {
    title: "Notices who stopped talking",
    body: "It tracks airtime and tone per participant. When the person who will actually decide has been quiet for ninety seconds, the earpiece says so — once, never two nudges at a time.",
    cite: "In the reference call, the spouse holds 6% of airtime.",
  },
  {
    title: "An audit record you can hand to compliance",
    body: "Every session writes an append-only log: speaker-attributed, PII-free, with the regulation cited beside each finding and the latency it was delivered at.",
    cite: "Written as JSONL, one line per event.",
  },
];

/* -------------------------------------------------------------- how it works */

export const steps = [
  {
    title: "Audio arrives from the room",
    body: "A single shared microphone streams to AssemblyAI over a WebSocket. Turn detection decides when someone has actually finished a sentence, rather than guessing from silence.",
  },
  {
    title: "Every word gets a speaker",
    body: "Streaming diarization labels words as they arrive and the dominant speaker owns the turn. Interim results update the live transcript but never reach the compliance path — nobody should be warned about half a sentence.",
  },
  {
    title: "Sensitive data is removed first",
    body: "Redaction runs before anything else touches the text. There is no code path in which raw personal data reaches the audit log, the interface, or a language model.",
  },
  {
    title: "The rule engine answers immediately",
    body: "The redacted turn is matched against the rule pack. A hit becomes a warning in the earpiece with the regulation and a sentence the professional can say out loud to correct course.",
  },
  {
    title: "A language model looks again, in parallel",
    body: "The same turn goes to a model with the conversation so far. Its findings arrive a few seconds later and are marked as such — useful, but never allowed to hold up the fast path.",
  },
  {
    title: "The agent decides whether to speak",
    body: "If the turn was addressed to it, it answers aloud from the client record in one or two sentences. Otherwise it says nothing and writes the turn to the audit log.",
  },
];

/* ---------------------------------------------------------------- use cases */

export const useCases = [
  {
    who: "Registered investment advisers",
    title: "Retail advice calls with a spouse in the room",
    body: "Suitability, fee disclosure and performance claims are all decided by exactly what was said out loud. When a second household member is present, the person who kills the deal is usually the one who stopped talking twenty minutes ago.",
    outcome: "Warnings on promissory language and pressure tactics, plus a clean record of who was told what.",
    lines: [
      { role: "advisor" as const, who: "Advisor", text: "This one you can't lose on.", flag: "can't lose" },
      { role: "spouse" as const, who: "Spouse", text: "What happens if the market drops?" },
    ],
    whisper: { sev: "critical" as const, head: "Implied no-loss guarantee", rule: "FINRA Rule 2210(d)(1)(B)" },
  },
  {
    who: "Clinical intake teams",
    title: "A patient, a caregiver and a clinician",
    body: "Intake conversations routinely include an adult child who answers on the patient's behalf. Attribution matters clinically and legally, and the transcript is full of protected health information from the first minute.",
    outcome: "Speaker-attributed notes with identifiers stripped before storage, and a nudge when the patient stops answering for themselves.",
    lines: [
      { role: "client" as const, who: "Patient", text: "My date of birth is March 14, 1962.", redact: "March 14, 1962" },
      { role: "spouse" as const, who: "Daughter", text: "She's also on two medications for her blood pressure." },
    ],
    whisper: { sev: "coach" as const, head: "Patient has not answered directly in 4 minutes", rule: "Attribution check" },
  },
  {
    who: "Insurance claims",
    title: "First notice of loss, taken by phone",
    body: "The adjuster is capturing dates, amounts and locations while a distressed claimant talks, often with a family member interjecting. Missed details mean a callback; a recorded misstatement means a complaint.",
    outcome: "Entities captured as they are spoken, policy numbers redacted, and a prompt when a required disclosure has not been read.",
    lines: [
      { role: "client" as const, who: "Claimant", text: "The policy number is 88991234567.", redact: "88991234567" },
      { role: "advisor" as const, who: "Adjuster", text: "I'll get that logged right now." },
    ],
    whisper: { sev: "warning" as const, head: "Recorded-line disclosure not yet given", rule: "State claims handling" },
  },
  {
    who: "Legal intake",
    title: "Consultations where scope has to stay clear",
    body: "An intake call has to gather enough to assess a matter without crossing into advice before an engagement exists. That line is crossed in a sentence, and nobody notices until the transcript is read back.",
    outcome: "A private flag the moment the conversation moves from assessment to counsel, with the phrasing to reset expectations.",
    lines: [
      { role: "advisor" as const, who: "Intake", text: "You should definitely file before the end of the month.", flag: "should definitely file" },
      { role: "client" as const, who: "Caller", text: "So I've got a case then?" },
    ],
    whisper: { sev: "warning" as const, head: "Advice given before engagement", rule: "Scope of representation" },
  },
];

/* --------------------------------------------------------------------- faq */

export const faqs = [
  {
    q: "How is this different from a meeting notetaker?",
    a: "A notetaker tells you what happened after it happened. Second Chair intervenes during the conversation — the warning about a prohibited phrase arrives while the professional is still in the sentence, in time to correct it. The record it produces afterwards is a by-product, not the point.",
  },
  {
    q: "Does the client hear the warnings?",
    a: "No. Warnings go to a private channel intended for an earpiece. In the browser demo that channel is panned hard left so you can hear the separation with headphones on; in a real deployment it is a separate audio device. The room channel is the only thing anyone else hears, and it only ever speaks when the agent is addressed by name.",
  },
  {
    q: "What stops it interrupting a normal conversation?",
    a: "An addressivity check runs on every finalised turn and is deliberately biased toward silence. It answers a direct address, and it recognises that being talked about in the third person is not a summons. Across the twenty-turn reference call, the agent speaks aloud twice and stays silent eighteen times.",
  },
  {
    q: "How fast is the warning, really?",
    a: "The rule tier measures 0 ms across a full call and is budgeted at under 15 ms per scan, because it is deterministic pattern matching running locally with no network call. The contextual review that follows takes a few seconds and is labelled as a second-tier finding, so it is never counted against the fast path.",
  },
  {
    q: "Where does personal data go?",
    a: "Redaction is the first stage of the pipeline, before compliance, before display, before storage, and before any model sees the text. Social security numbers spoken digit by digit are caught alongside written ones. There is no configuration in which raw personal data reaches the audit log.",
  },
  {
    q: "Which speech and language models does it use?",
    a: "Transcription and real-time diarization run on AssemblyAI's Universal-Streaming API. The contextual review and the spoken answers run on a language model through one of three interchangeable providers — Groq, the AssemblyAI LLM Gateway, or Anthropic directly — chosen by whichever credential is present.",
  },
  {
    q: "What happens if the language model is unavailable?",
    a: "The call continues. The contextual tier is best-effort by design: a rate limit or an outage costs one nuanced finding, never the session. The deterministic rule tier requires no model at all and keeps catching every pattern violation.",
  },
  {
    q: "Can the rule pack be changed?",
    a: "Yes. Rules are a YAML file — an identifier, a severity, the regulation cited, the phrasing to suggest, and the patterns that trigger it. The nine shipped rules are a credible FINRA and SEC starting point for demonstration, not a compliance product. A real deployment needs a pack reviewed by counsel.",
  },
  {
    q: "Is it production ready?",
    a: "The pipeline is real and covered by 130 automated tests, and the demo you can open is the actual system, not a recording. It is a hackathon build: the client record is a fixture rather than a CRM integration, and live microphone mode assumes one shared room microphone rather than per-speaker channels.",
  },
  {
    q: "Why is the demo slow to load?",
    a: "It runs on a free container that sleeps after about fifteen minutes of inactivity, so the first request has to wake it — roughly forty seconds. Everything after that is instant. The status indicator on this page tells you which state it is in before you click.",
  },
];

/* -------------------------------------------------------------------- specs */

export const specs: [string, string][] = [
  ["Transcription", "AssemblyAI Universal-Streaming v3 over WebSocket, universal-3-5-pro"],
  ["Speaker separation", "Streaming diarization with per-word labels, up to 10 speakers"],
  ["Rule tier", "Deterministic pattern engine, 9 FINRA and SEC rules, 0 ms measured"],
  ["Contextual tier", "Groq, AssemblyAI LLM Gateway, or Anthropic — whichever key is present"],
  ["Redaction", "Local and deterministic, runs before storage, display, or inference"],
  ["Transport", "FastAPI with a session WebSocket, one container serving app and interface"],
  ["Audit record", "Append-only JSONL, speaker-attributed, PII-free, regulation cited"],
  ["Test coverage", "130 automated tests, no network calls required"],
];
