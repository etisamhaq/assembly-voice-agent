import type { ReactNode } from "react";

export type Line = {
  role: "advisor" | "client" | "spouse" | "agent";
  who: string;
  text: string;
  flag?: string;
  redact?: string;
};

/** Renders a spoken line, marking a flagged phrase or a redacted identifier. */
export function TurnLine({ line, animate }: { line: Line; animate?: boolean }) {
  return (
    <div className={`turn ${line.role}${line.flag ? " flag" : ""}${animate ? " enter" : ""}`}>
      <div className="who">{line.who}</div>
      <div className="said">{decorate(line)}</div>
    </div>
  );
}

function decorate(line: Line): ReactNode {
  const needle = line.flag ?? line.redact;
  if (!needle) return line.text;

  const at = line.text.indexOf(needle);
  if (at === -1) return line.text;

  const before = line.text.slice(0, at);
  const after = line.text.slice(at + needle.length);
  const piece = line.flag ? (
    <mark>{needle}</mark>
  ) : (
    <span className="redacted">redacted</span>
  );

  return (
    <>
      {before}
      {piece}
      {after}
    </>
  );
}

export function WhisperCard({
  sev,
  head,
  rule,
  say,
  ms,
  animate,
}: {
  sev: "critical" | "warning" | "coach";
  head: string;
  rule: string;
  say?: string;
  ms?: string;
  animate?: boolean;
}) {
  return (
    <div className={`wcard ${sev}${animate ? " enter-w" : ""}`}>
      <div className="wtop">
        <span>{sev}</span>
        {ms ? <span className="ms">{ms}</span> : null}
      </div>
      <div className="whead">{head}</div>
      {say ? <div className="wsay">{say}</div> : null}
      <div className="wreg">{rule}</div>
    </div>
  );
}

export function Console({
  label,
  children,
  action,
}: {
  label: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="console">
      <div className="console-bar">
        <span className="live-dot" aria-hidden="true" />
        <span>{label}</span>
        {action}
      </div>
      {children}
    </div>
  );
}
