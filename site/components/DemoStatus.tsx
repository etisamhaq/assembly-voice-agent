"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/content";

type State = "checking" | "live" | "waking" | "down";

const COPY: Record<State, string> = {
  checking: "Checking the backend",
  live: "Backend ready",
  waking: "Waking the backend, about 40s",
  down: "Backend unreachable",
};

/**
 * The demo runs on a container that sleeps when idle, so a first-time visitor
 * can click and watch nothing happen for forty seconds. Say which it is first.
 */
export default function DemoStatus({ className = "" }: { className?: string }) {
  const [state, setState] = useState<State>("checking");
  const [detail, setDetail] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    const ping = (ms: number) => {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), ms);
      return fetch(`${API_URL}/api/health`, { signal: ctl.signal, cache: "no-store" })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .finally(() => clearTimeout(timer));
    };

    (async () => {
      try {
        // A sleeping container answers slowly rather than failing, so a short
        // first attempt distinguishes "awake" from "waking".
        const body = await ping(4000);
        if (!cancelled) {
          setState("live");
          setDetail(`${body.rules_loaded} rules loaded`);
        }
        return;
      } catch {
        if (cancelled) return;
        setState("waking");
      }

      try {
        const body = await ping(75000);
        if (!cancelled) {
          setState("live");
          setDetail(`${body.rules_loaded} rules loaded`);
        }
      } catch {
        if (!cancelled) setState("down");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <span className={`status ${className}`} data-state={state} role="status" aria-live="polite">
      <span className="dot" aria-hidden="true" />
      <span>
        {COPY[state]}
        {state === "live" && detail ? ` · ${detail}` : ""}
      </span>
    </span>
  );
}
