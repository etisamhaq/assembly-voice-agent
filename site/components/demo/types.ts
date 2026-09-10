export type Role = "advisor" | "client" | "spouse" | "unknown";
export type Severity = "critical" | "warning" | "coach" | "info";

export interface Violation {
  rule_id: string;
  title: string;
  severity: Severity;
  regulation: string;
  detail: string;
  suggested_phrasing: string;
  source: string;
  quote: string;
}

export interface TurnPayload {
  order: number;
  speaker: string;
  role: Role;
  text: string;
  start_ms: number;
  end_ms: number;
  confidence: number;
}

export interface TurnEvent {
  type: "turn.processed";
  turn: TurnPayload;
  redactions: { kind: string; count: number }[];
  violations: Violation[];
  addressed_to_agent: boolean;
  fast_path_ms: number;
}

export interface WhisperEvent {
  type: "whisper";
  id: string;
  severity: Severity;
  headline: string;
  detail: string;
  suggested_phrasing: string;
  rule_id: string;
  latency_ms: number;
  tier: number;
  over_budget: boolean;
  audio_b64?: string | null;
}

export interface RoomEvent {
  type: "room";
  id: string;
  text: string;
  latency_ms: number;
  audio_b64?: string | null;
}

export interface SessionEnd {
  type: "session.end";
  turns: number;
  violations: number;
  whispers: number;
  room_replies: number;
  redactions: number;
  budget_misses: number;
  max_fast_path_ms: number;
  violations_by_severity: Partial<Record<Severity, number>>;
  airtime: Partial<Record<Role, number>>;
}

export interface Capabilities {
  llm_judge: boolean;
  room_agent: boolean;
  server_tts: boolean;
  live_audio?: boolean;
}

/** A line in the transcript column — finalized, or still being spoken. */
export interface Line {
  order: number;
  role: Role;
  text: string;
  clock: string;
  final: boolean;
  violations: Violation[];
  redactions: string[];
  addressed: boolean;
}

export type Status = "idle" | "connecting" | "running" | "ended" | "error";
