"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/content";
import { playPanned, speakLocal, startMic, audioContext, type MicHandle } from "./audio";
import type {
  Capabilities, Line, RoomEvent, SessionEnd, Severity, Status, TurnEvent, WhisperEvent,
} from "./types";

const NAMES: Record<string, string> = {
  advisor: "Marcus, advisor",
  client: "Dana, client",
  spouse: "Sam, spouse",
  unknown: "Unknown speaker",
};

function clock(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export interface SessionState {
  status: Status;
  error: string;
  title: string;
  capabilities: Capabilities | null;
  lines: Line[];
  whispers: WhisperEvent[];
  room: RoomEvent[];
  summary: SessionEnd | null;
  stats: { turns: number; violations: number; redactions: number; worst: number };
}

const EMPTY: SessionState = {
  status: "idle",
  error: "",
  title: "",
  capabilities: null,
  lines: [],
  whispers: [],
  room: [],
  summary: null,
  stats: { turns: 0, violations: 0, redactions: 0, worst: 0 },
};

export function speakerName(role: string): string {
  return NAMES[role] ?? role;
}

/**
 * Owns the session socket. The backend is a separate origin that serves no
 * pages, so everything here is driven by the event stream it sends.
 */
export function useSession() {
  const [state, setState] = useState<SessionState>(EMPTY);
  const ws = useRef<WebSocket | null>(null);
  const mic = useRef<MicHandle | null>(null);
  const closing = useRef(false);

  const teardown = useCallback(() => {
    mic.current?.stop();
    mic.current = null;
    if (ws.current) {
      closing.current = true;
      ws.current.close();
      ws.current = null;
    }
  }, []);

  useEffect(() => teardown, [teardown]);

  const stop = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "stop" }));
    }
    teardown();
    setState((s) => (s.status === "running" ? { ...s, status: "ended" } : s));
  }, [teardown]);

  const start = useCallback(
    async (mode: "simulated" | "live", speed: string) => {
      teardown();
      closing.current = false;
      audioContext(); // unlock playback inside the click handler
      setState({ ...EMPTY, status: "connecting" });

      const base = API_URL.replace(/^http/, "ws");
      const socket = new WebSocket(`${base}/ws/session?mode=${mode}&speed=${speed}`);
      socket.binaryType = "arraybuffer";
      ws.current = socket;

      socket.onopen = async () => {
        setState((s) => ({ ...s, status: "running" }));
        if (mode === "live") {
          try {
            mic.current = await startMic(socket);
          } catch (e) {
            setState((s) => ({
              ...s,
              error: `Microphone unavailable: ${(e as Error).message}`,
            }));
          }
        }
      };

      socket.onerror = () =>
        setState((s) => ({
          ...s,
          status: "error",
          error: "Could not reach the backend. It sleeps when idle — wait a moment and retry.",
        }));

      socket.onclose = () => {
        if (closing.current) return;
        setState((s) =>
          s.status === "running" || s.status === "connecting"
            ? { ...s, status: s.summary ? "ended" : "error",
                error: s.summary ? "" : "The connection closed before the call finished." }
            : s,
        );
      };

      socket.onmessage = (m) => {
        const ev = JSON.parse(m.data as string);

        switch (ev.type) {
          case "session.begin":
            setState((s) => ({ ...s, title: ev.title, capabilities: ev.capabilities }));
            break;

          case "transcript.partial":
            setState((s) => {
              const lines = [...s.lines];
              const at = lines.findIndex((l) => l.order === ev.order && !l.final);
              const line: Line = {
                order: ev.order, role: ev.role, text: ev.text, clock: "",
                final: false, violations: [], redactions: [], addressed: false,
              };
              if (at === -1) lines.push(line);
              else lines[at] = line;
              return { ...s, lines };
            });
            break;

          case "turn.processed": {
            const e = ev as TurnEvent;
            setState((s) => {
              const lines = s.lines.filter((l) => !(l.order === e.turn.order && !l.final));
              lines.push({
                order: e.turn.order,
                role: e.turn.role,
                text: e.turn.text,
                clock: clock(e.turn.start_ms),
                final: true,
                violations: e.violations,
                redactions: e.redactions.map((r) => r.kind),
                addressed: e.addressed_to_agent,
              });
              return {
                ...s,
                lines,
                stats: {
                  turns: s.stats.turns + 1,
                  violations: s.stats.violations + e.violations.length,
                  redactions: s.stats.redactions + e.redactions.reduce((a, r) => a + r.count, 0),
                  worst: Math.max(s.stats.worst, e.fast_path_ms),
                },
              };
            });
            break;
          }

          case "whisper": {
            const e = ev as WhisperEvent;
            if (e.audio_b64) void playPanned(e.audio_b64, -1);
            else speakLocal(`${e.headline}. ${e.suggested_phrasing || e.detail || ""}`, true);
            setState((s) => ({ ...s, whispers: [...s.whispers, e] }));
            break;
          }

          case "room": {
            const e = ev as RoomEvent;
            if (e.audio_b64) void playPanned(e.audio_b64, 0);
            else speakLocal(e.text, false);
            setState((s) => ({ ...s, room: [...s.room, e] }));
            break;
          }

          case "session.end":
            setState((s) => ({ ...s, summary: ev as SessionEnd, status: "ended" }));
            break;
        }
      };
    },
    [teardown],
  );

  return { ...state, start, stop };
}

export const SEVERITY_ORDER: Severity[] = ["critical", "warning", "coach", "info"];
