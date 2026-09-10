"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { transcript } from "@/lib/content";
import { TurnLine, WhisperCard } from "./Console";

const GAP_PLAIN = 1150;
const GAP_FLAGGED = 1750;
const WHISPER_LAG = 300;

/**
 * The one orchestrated moment on the site: a real excerpt of the reference
 * call, with each warning landing beside the line that caused it. The lag
 * between the two is the product, so it is timed rather than instant.
 */
export default function HeroTranscript() {
  const [shown, setShown] = useState(0);
  const [whispers, setWhispers] = useState(0);
  const [running, setRunning] = useState(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const roomRef = useRef<HTMLDivElement>(null);

  const clear = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  const play = useCallback(() => {
    clear();

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(transcript.length);
      setWhispers(transcript.filter((t) => t.whisper).length);
      setRunning(false);
      return;
    }

    setShown(0);
    setWhispers(0);
    setRunning(true);

    let at = 260;
    let whisperCount = 0;
    transcript.forEach((turn, i) => {
      timers.current.push(setTimeout(() => setShown(i + 1), at));
      if (turn.whisper) {
        whisperCount += 1;
        const n = whisperCount;
        timers.current.push(setTimeout(() => setWhispers(n), at + WHISPER_LAG));
      }
      at += turn.whisper ? GAP_FLAGGED : GAP_PLAIN;
    });
    timers.current.push(setTimeout(() => setRunning(false), at));
  }, [clear]);

  useEffect(() => {
    play();
    return clear;
  }, [play, clear]);

  // Keep the newest line in view as the call plays.
  useEffect(() => {
    const el = roomRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [shown]);

  const visible = transcript.slice(0, shown);
  const cards = transcript.filter((t) => t.whisper).slice(0, whispers);

  return (
    <div className="console">
      <div className="console-bar">
        <span className={`live-dot${running ? " on" : ""}`} aria-hidden="true" />
        <span>401(k) rollover review — three people in the room</span>
        <button className="replay" onClick={play}>
          {running ? "Playing" : "Replay"}
        </button>
      </div>

      <div className="console-body">
        <div className="console-room" ref={roomRef}>
          {visible.length === 0 ? (
            <p className="console-empty">Waiting for the first turn.</p>
          ) : (
            visible.map((t, i) => <TurnLine key={i} line={t} animate />)
          )}
        </div>

        <div className="console-whisper">
          <div className="whisper-head">Advisor&rsquo;s earpiece — nobody else hears this</div>
          {cards.length === 0 ? (
            <p className="console-empty">Nothing to flag yet.</p>
          ) : (
            cards.map((t, i) => (
              <WhisperCard
                key={i}
                sev={t.whisper!.sev}
                head={t.whisper!.head}
                rule={t.whisper!.rule}
                say={t.whisper!.say}
                ms={t.whisper!.ms}
                animate
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
