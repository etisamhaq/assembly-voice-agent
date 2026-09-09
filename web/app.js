/* Second Chair console.
 *
 * The one non-obvious bit: whisper audio is panned hard left and room audio is
 * centred. With headphones on, the two channels are physically distinguishable
 * - which is the entire premise of the product, and the thing a screenshot
 * cannot convey.
 */

const $ = (id) => document.getElementById(id);

const el = {
  transcript: $("transcript"), whispers: $("whispers"), roomFeed: $("roomFeed"),
  title: $("sessionTitle"), caps: $("caps"), dot: $("liveDot"),
  start: $("startBtn"), stop: $("stopBtn"), mode: $("mode"), speed: $("speed"),
  sTurns: $("sTurns"), sViol: $("sViol"), sRedact: $("sRedact"),
  sWhisper: $("sWhisper"), sRoom: $("sRoom"), sLat: $("sLat"),
  airA: $("airA"), airC: $("airC"), airS: $("airS"),
};

const NAMES = { advisor: "Marcus (advisor)", client: "Dana (client)", spouse: "Sam (spouse)", unknown: "Unknown" };

let ws = null;
let audioCtx = null;
let mic = null;
let stats = { turns: 0, violations: 0, redactions: 0, whispers: 0, room: 0, worst: 0 };
const partials = new Map();

/* ----------------------------------------------------------------- audio */

function ctx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}

/** Play base64 mp3 through a stereo panner. pan -1 = left ear only. */
async function playPanned(b64, pan) {
  try {
    const c = ctx();
    const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
    const buf = await c.decodeAudioData(bytes.buffer);
    const src = c.createBufferSource();
    src.buffer = buf;
    const panner = c.createStereoPanner();
    panner.pan.value = pan;
    src.connect(panner).connect(c.destination);
    src.start();
  } catch (e) { console.warn("audio playback failed", e); }
}

/** No server TTS: fall back to the browser voice. Cannot be panned, so the
 *  whisper voice is pitched and sped up instead to stay distinguishable. */
function speakLocal(text, isWhisper) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = isWhisper ? 1.35 : 1.02;
  u.pitch = isWhisper ? 1.25 : 0.95;
  u.volume = isWhisper ? 0.85 : 1.0;
  speechSynthesis.speak(u);
}

/* ------------------------------------------------------------------ util */

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Wrap [X_REDACTED] placeholders and any violation quotes for display. */
function renderText(text, violations) {
  let html = esc(text).replace(/\[([A-Z_]+)_REDACTED\]/g,
    (_, k) => `<span class="redact">${k}</span>`);
  for (const v of violations || []) {
    if (!v.quote) continue;
    const q = esc(v.quote);
    const idx = html.indexOf(q);
    if (idx === -1) continue;
    html = html.slice(0, idx) + `<mark class="hit ${esc(v.severity)}">${q}</mark>` + html.slice(idx + q.length);
  }
  return html;
}

function clearEmpty(node) {
  const e = node.querySelector(".empty");
  if (e) e.remove();
}

const atBottom = (n) => n.scrollHeight - n.scrollTop - n.clientHeight < 90;
function pin(node, wasBottom) { if (wasBottom) node.scrollTop = node.scrollHeight; }

/* --------------------------------------------------------------- render */

function renderPartial(ev) {
  const wasBottom = atBottom(el.transcript);
  clearEmpty(el.transcript);
  let node = partials.get(ev.order);
  if (!node) {
    node = document.createElement("div");
    node.className = `turn partial role-${ev.role}`;
    node.innerHTML = `<div class="turn-meta"><span class="who">${esc(NAMES[ev.role] || ev.role)}</span>
      <span class="t">speaking…</span></div><div class="turn-text"></div>`;
    el.transcript.appendChild(node);
    partials.set(ev.order, node);
  }
  node.querySelector(".turn-text").innerHTML = renderText(ev.text, []);
  pin(el.transcript, wasBottom);
}

function renderTurn(ev) {
  const wasBottom = atBottom(el.transcript);
  clearEmpty(el.transcript);
  const t = ev.turn;
  const node = partials.get(t.order) || document.createElement("div");
  partials.delete(t.order);

  const worst = (ev.violations || []).find((v) => v.severity === "critical")
    ? "flagged" : (ev.violations || []).length ? "flagged-warning" : "";
  node.className = `turn role-${t.role} ${worst}`.trim();

  const secs = Math.floor(t.start_ms / 1000);
  const clock = `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
  const redTag = (ev.redactions || []).length
    ? ` <span class="t" style="color:var(--room)">· ${ev.redactions.map((r) => r.kind).join(", ")} redacted</span>` : "";
  const addressed = ev.addressed_to_agent
    ? ` <span class="t" style="color:var(--room)">· addressed agent</span>` : "";

  node.innerHTML = `<div class="turn-meta"><span class="who">${esc(NAMES[t.role] || t.role)}</span>
    <span class="t">${clock}</span>${redTag}${addressed}</div>
    <div class="turn-text">${renderText(t.text, ev.violations)}</div>`;

  if (!node.parentNode) el.transcript.appendChild(node);

  stats.turns += 1;
  stats.violations += (ev.violations || []).length;
  stats.redactions += (ev.redactions || []).reduce((a, r) => a + r.count, 0);
  stats.worst = Math.max(stats.worst, ev.fast_path_ms || 0);
  paintStats();
  pin(el.transcript, wasBottom);
}

function renderWhisper(ev) {
  const wasBottom = atBottom(el.whispers);
  clearEmpty(el.whispers);
  const node = document.createElement("div");
  node.className = `whisper ${ev.severity}`;
  node.innerHTML = `
    <div class="w-top">
      <span class="w-sev">${esc(ev.severity)}</span>
      <span style="color:var(--dim)">${esc(ev.rule_id)}</span>
      <span class="w-lat ${ev.over_budget ? "over" : ""}">${ev.tier === 2 ? "tier 2 · " : ""}${ev.latency_ms}ms</span>
    </div>
    <div class="w-head">${esc(ev.headline)}</div>
    ${ev.detail ? `<div class="w-detail">${esc(ev.detail)}</div>` : ""}
    ${ev.suggested_phrasing ? `<div class="w-say">${esc(ev.suggested_phrasing)}</div>` : ""}`;
  el.whispers.appendChild(node);

  if (ev.audio_b64) playPanned(ev.audio_b64, -1);      // hard left: the earpiece
  else speakLocal(`${ev.headline}. ${ev.suggested_phrasing || ev.detail || ""}`, true);

  stats.whispers += 1;
  paintStats();
  pin(el.whispers, wasBottom);
}

function renderRoom(ev) {
  clearEmpty(el.roomFeed);
  const node = document.createElement("div");
  node.className = "room-line";
  node.innerHTML = `<div class="icon">SC</div><div class="txt">${esc(ev.text)}</div>
    <div class="lat">${ev.latency_ms}ms</div>`;
  el.roomFeed.appendChild(node);
  el.roomFeed.scrollTop = el.roomFeed.scrollHeight;

  if (ev.audio_b64) playPanned(ev.audio_b64, 0);       // centre: the room
  else speakLocal(ev.text, false);

  stats.room += 1;
  paintStats();
}

function paintStats() {
  el.sTurns.textContent = stats.turns;
  el.sViol.textContent = stats.violations;
  el.sViol.className = "v" + (stats.violations ? " crit" : "");
  el.sRedact.textContent = stats.redactions;
  el.sWhisper.textContent = stats.whispers;
  el.sRoom.textContent = stats.room;
  el.sLat.textContent = `${stats.worst}ms`;
  el.sLat.className = "v " + (stats.worst > 1000 ? "crit" : "ok");
}

function paintAirtime(a) {
  const pct = (v) => `${Math.round((v || 0) * 100)}%`;
  el.airA.style.width = pct(a.advisor);
  el.airC.style.width = pct(a.client);
  el.airS.style.width = pct(a.spouse);
}

function paintCaps(caps) {
  const label = { llm_judge: "LLM judge", room_agent: "room agent", server_tts: "voice", live_audio: "live audio" };
  el.caps.innerHTML = Object.entries(caps)
    .map(([k, v]) => `<span class="pill ${v ? "on" : "off"}">${label[k] || k}${v ? "" : " off"}</span>`)
    .join("");
}

/* -------------------------------------------------------------- session */

async function startMic(socket) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
  });
  const c = ctx();
  const source = c.createMediaStreamSource(stream);
  // ScriptProcessor is deprecated but universally available and adequate here;
  // swap for an AudioWorklet if you need lower jitter.
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
  mic = { stream, proc, source };
}

function stopMic() {
  if (!mic) return;
  mic.proc.disconnect();
  mic.source.disconnect();
  mic.stream.getTracks().forEach((t) => t.stop());
  mic = null;
}

function reset() {
  el.transcript.innerHTML = "";
  el.whispers.innerHTML = "";
  el.roomFeed.innerHTML = "";
  partials.clear();
  stats = { turns: 0, violations: 0, redactions: 0, whispers: 0, room: 0, worst: 0 };
  paintStats();
  paintAirtime({});
}

async function start() {
  reset();
  ctx();  // unlock audio inside the click handler
  const mode = el.mode.value;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/session?mode=${mode}&speed=${el.speed.value}`);
  ws.binaryType = "arraybuffer";

  ws.onopen = async () => {
    el.start.disabled = true;
    el.stop.disabled = false;
    el.dot.classList.add("live");
    if (mode === "live") {
      try { await startMic(ws); }
      catch (e) { alert("Microphone unavailable: " + e.message); }
    }
  };

  ws.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    switch (ev.type) {
      case "session.begin":
        el.title.textContent = ev.title;
        paintCaps(ev.capabilities);
        break;
      case "transcript.partial": renderPartial(ev); break;
      case "turn.processed":     renderTurn(ev); break;
      case "whisper":            renderWhisper(ev); break;
      case "room":               renderRoom(ev); break;
      case "session.end":
        paintAirtime(ev.airtime || {});
        el.title.textContent += "  ·  call ended";
        break;
      case "audit.ready":
        el.title.textContent += `  ·  audit → ${ev.path.split("/").pop()}`;
        break;
    }
  };

  ws.onclose = () => {
    el.start.disabled = false;
    el.stop.disabled = true;
    el.dot.classList.remove("live");
    stopMic();
  };
}

function stop() {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "stop" }));
  stopMic();
  if (ws) ws.close();
}

el.start.addEventListener("click", start);
el.stop.addEventListener("click", stop);

fetch("/api/health").then((r) => r.json()).then((h) => {
  paintCaps(h.capabilities);
  if (!h.capabilities.live_audio) {
    el.mode.querySelector('option[value="live"]').textContent = "Live mic (no API key)";
    el.mode.querySelector('option[value="live"]').disabled = true;
  }
  // ?autostart=1&speed=10 - for screen recording and headless capture.
  const q = new URLSearchParams(location.search);
  if (q.has("autostart")) {
    if (q.has("speed")) {
      const want = q.get("speed");
      if ([...el.speed.options].some((o) => o.value === want)) el.speed.value = want;
    }
    if (q.has("mode")) el.mode.value = q.get("mode");
    start();
  }
}).catch(() => {});
