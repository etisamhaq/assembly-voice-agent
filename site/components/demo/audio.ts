/**
 * The two channels, made audible.
 *
 * Whisper audio is panned hard left and room audio sits centre, so with
 * headphones on the separation is something you hear rather than read. That is
 * the whole premise of the product and the one thing a screenshot cannot show.
 */

let ctx: AudioContext | null = null;

export function audioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) ctx = new Ctor();
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

/** Play base64 mp3 through a stereo panner. pan -1 is the left ear only. */
export async function playPanned(b64: string, pan: number): Promise<void> {
  const c = audioContext();
  if (!c) return;
  try {
    const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
    const buf = await c.decodeAudioData(bytes.buffer as ArrayBuffer);
    const src = c.createBufferSource();
    src.buffer = buf;
    const panner = c.createStereoPanner();
    panner.pan.value = pan;
    src.connect(panner).connect(c.destination);
    src.start();
  } catch {
    /* A failed cue must never interrupt the call. */
  }
}

/**
 * Without server-side speech the browser voice stands in. It cannot be panned,
 * so the whisper voice is pitched up and sped up instead to stay distinct.
 */
export function speakLocal(text: string, isWhisper: boolean): void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = isWhisper ? 1.35 : 1.02;
  u.pitch = isWhisper ? 1.25 : 0.95;
  u.volume = isWhisper ? 0.85 : 1;
  window.speechSynthesis.speak(u);
}

export interface MicHandle {
  stop: () => void;
}

/** Capture the room microphone as 16kHz mono PCM and stream it to the socket. */
export async function startMic(socket: WebSocket): Promise<MicHandle> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const c = audioContext();
  if (!c) throw new Error("Web Audio is unavailable in this browser");

  const source = c.createMediaStreamSource(stream);
  // ScriptProcessor is deprecated but universally available and adequate here;
  // an AudioWorklet would lower jitter if that ever matters.
  const proc = c.createScriptProcessor(4096, 1, 1);
  const ratio = c.sampleRate / 16000;

  proc.onaudioprocess = (e) => {
    if (socket.readyState !== WebSocket.OPEN) return;
    const input = e.inputBuffer.getChannelData(0);
    const outLen = Math.floor(input.length / ratio);
    const pcm = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const s = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)]));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    socket.send(pcm.buffer);
  };

  source.connect(proc);
  proc.connect(c.destination);

  return {
    stop() {
      proc.disconnect();
      source.disconnect();
      stream.getTracks().forEach((t) => t.stop());
    },
  };
}
