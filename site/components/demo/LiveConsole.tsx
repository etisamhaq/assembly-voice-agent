"use client";

import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { speakerName, useSession } from "./useSession";
import type { Line, Severity, Violation } from "./types";

const REDACTED = /\[([A-Z_]+)_REDACTED\]/g;

/** Marks redaction placeholders and any flagged phrase inside a spoken line. */
function renderText(text: string, violations: Violation[]): ReactNode {
  const quote = violations.find((v) => v.quote && text.includes(v.quote));

  const withRedactions = (chunk: string, keyBase: string): ReactNode[] => {
    const out: ReactNode[] = [];
    let last = 0;
    for (const m of chunk.matchAll(REDACTED)) {
      if (m.index! > last) out.push(chunk.slice(last, m.index));
      out.push(
        <span className="redact" key={`${keyBase}-r-${m.index}`}>
          {m[1].toLowerCase()}
        </span>,
      );
      last = m.index! + m[0].length;
    }
    if (last < chunk.length) out.push(chunk.slice(last));
    return out;
  };

  if (!quote) return withRedactions(text, "t");

  const at = text.indexOf(quote.quote);
  return (
    <>
      {withRedactions(text.slice(0, at), "a")}
      <mark className={`hit ${quote.severity}`}>{quote.quote}</mark>
      {withRedactions(text.slice(at + quote.quote.length), "b")}
    </>
  );
}

function TurnRow({ line }: { line: Line }) {
  const worst = line.violations.some((v) => v.severity === "critical")
    ? " flagged"
    : line.violations.length
      ? " flagged-warning"
      : "";

  return (
    <div className={`d-turn role-${line.role}${worst}${line.final ? "" : " partial"}`}>
      <div className="d-meta">
        <span className="who">{speakerName(line.role)}</span>
        <span className="t">{line.final ? line.clock : "speaking"}</span>
        {line.redactions.length > 0 && (
          <span className="tag">{line.redactions.join(", ")} redacted</span>
        )}
        {line.addressed && <span className="tag">addressed agent</span>}
      </div>
      <div className="d-said">{renderText(line.text, line.violations)}</div>
    </div>
  );
}

export default function LiveConsole() {
  const s = useSession();
  const [mode, setMode] = useState<"simulated" | "live">("simulated");
  const [speed, setSpeed] = useState("4");
  const roomRef = useRef<HTMLDivElement>(null);
  const whisperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = roomRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [s.lines.length]);

  useEffect(() => {
    const el = whisperRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [s.whispers.length]);

  const running = s.status === "running" || s.status === "connecting";
  const liveDisabled = s.capabilities?.live_audio === false;

  return (
    <div className="demo">
      <div className="demo-controls">
        <label className="field">
          <span>Source</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as "simulated" | "live")} disabled={running}>
            <option value="simulated">Scripted call</option>
            <option value="live" disabled={liveDisabled}>Live microphone</option>
          </select>
        </label>

        <label className="field">
          <span>Pace</span>
          <select value={speed} onChange={(e) => setSpeed(e.target.value)} disabled={running || mode === "live"}>
            <option value="0">Instant</option>
            <option value="1">Real time</option>
            <option value="4">4&times;</option>
            <option value="10">10&times;</option>
          </select>
        </label>

        <div className="demo-actions">
          {running ? (
            <button className="btn btn-ghost" onClick={s.stop}>Stop call</button>
          ) : (
            <button className="btn btn-primary" onClick={() => void s.start(mode, speed)}>
              {s.status === "ended" ? "Run it again" : "Start call"}
            </button>
          )}
        </div>
      </div>

      {s.error && (
        <div className="demo-error" role="alert">
          <strong>{s.error}</strong>
          <button className="btn btn-ghost" onClick={() => void s.start(mode, speed)}>Try again</button>
        </div>
      )}

      <div className="console">
        <div className="console-bar">
          <span className={`live-dot${s.status === "running" ? " on" : ""}`} aria-hidden="true" />
          <span>{s.title || "No session yet"}</span>
          <span className="bar-right">
            {s.capabilities && (
              <Fragment>
                <span className={`cap${s.capabilities.llm_judge ? " on" : ""}`}>contextual review</span>
                <span className={`cap${s.capabilities.server_tts ? " on" : ""}`}>voice</span>
              </Fragment>
            )}
          </span>
        </div>

        <div className="console-body">
          <div className="console-room" ref={roomRef}>
            <div className="col-label">The room — everyone hears this</div>
            {s.lines.length === 0 ? (
              <p className="console-empty">
                {s.status === "connecting"
                  ? "Connecting to the backend…"
                  : "Press Start call. Everything below is produced live by the pipeline."}
              </p>
            ) : (
              s.lines.map((l) => <TurnRow key={`${l.order}-${l.final}`} line={l} />)
            )}

            {s.summary && <SessionRecord summary={s.summary} />}
          </div>

          <div className="console-whisper" ref={whisperRef}>
            <div className="col-label">
              Earpiece — nobody else hears this
              <span className="legend">
                <span className="lg critical" /> violation
                <span className="lg warning" /> risky
                <span className="lg coach" /> coaching
              </span>
            </div>
            {s.whispers.length === 0 ? (
              <p className="console-empty">Warnings and coaching appear here.</p>
            ) : (
              s.whispers.map((w) => (
                <div className={`wcard ${w.severity}`} key={w.id}>
                  <div className="wtop">
                    <span>{w.severity}</span>
                    <span className="ms">
                      {w.tier === 2 ? "tier 2 · " : ""}
                      {w.latency_ms} ms
                    </span>
                  </div>
                  <div className="whead">{w.headline}</div>
                  {w.detail && <div className="wdetail">{w.detail}</div>}
                  {w.suggested_phrasing && <div className="wsay">{w.suggested_phrasing}</div>}
                  <div className="wreg">{w.rule_id}</div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="console-foot">
          <div className="col-label">Spoken aloud</div>
          {s.room.length === 0 ? (
            <p className="console-empty">The agent stays silent unless it is addressed by name.</p>
          ) : (
            s.room.map((r) => (
              <div className="room-line" key={r.id}>
                <span className="icon">SC</span>
                <span className="txt">{r.text}</span>
                <span className="lat">{r.latency_ms} ms</span>
              </div>
            ))
          )}
        </div>
      </div>

      <dl className="demo-stats">
        <Stat k="Turns" v={s.stats.turns} />
        <Stat k="Findings" v={s.stats.violations} tone={s.stats.violations ? "crit" : undefined} />
        <Stat k="Redacted" v={s.stats.redactions} />
        <Stat k="Spoken aloud" v={s.room.length} />
        <Stat k="Worst fast path" v={`${s.stats.worst} ms`} tone={s.stats.worst > 1000 ? "crit" : "ok"} />
      </dl>
    </div>
  );
}

function Stat({ k, v, tone }: { k: string; v: string | number; tone?: "crit" | "ok" }) {
  return (
    <div className="dstat">
      <dt>{k}</dt>
      <dd className={tone ?? ""}>{v}</dd>
    </div>
  );
}

function SessionRecord({ summary }: { summary: NonNullable<ReturnType<typeof useSession>["summary"]> }) {
  const sev = summary.violations_by_severity;
  const quietest = Object.entries(summary.airtime)
    .filter(([role]) => role !== "advisor")
    .sort((a, b) => (a[1] ?? 0) - (b[1] ?? 0))[0];

  const rows: [string, string | number, string?][] = [
    ["Turns on the record", summary.turns],
    ["Critical findings", sev.critical ?? 0, sev.critical ? "crit" : "ok"],
    ["Warnings", sev.warning ?? 0, sev.warning ? "warn" : "ok"],
    ["Coaching cues", sev.coach ?? 0],
    ["Identifiers redacted", summary.redactions],
    ["Spoken aloud by the agent", `${summary.room_replies} of ${summary.turns} turns`],
    ["Worst fast-path latency", `${summary.max_fast_path_ms} ms`, summary.budget_misses ? "crit" : "ok"],
  ];
  if (quietest) {
    rows.push(["Quietest participant", `${quietest[0]}, ${Math.round((quietest[1] ?? 0) * 100)}% of airtime`]);
  }

  return (
    <div className="record-card">
      <div className="rc-head">Session record</div>
      <div className="rc-grid">
        {rows.map(([k, v, tone]) => (
          <div className="rc-row" key={k}>
            <span className="k">{k}</span>
            <span className={`v ${tone ?? ""}`}>{v}</span>
          </div>
        ))}
      </div>
      <div className="rc-foot">
        Written to an append-only log — speaker-attributed, free of personal identifiers, with the
        regulation cited beside each finding.
      </div>
    </div>
  );
}

export type { Severity };
