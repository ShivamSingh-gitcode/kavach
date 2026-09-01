/* Kavach — browser presentation layer.
 * Backend remains the source of truth for stage, score and tier.
 * In audio modes, the WAV's HTML5 currentTime is the master clock:
 * SSE delivers timestamped backend events, and this UI reveals them when
 * audio reaches the corresponding segment start.
 */

const API_BASE = "";
const STAGE_LABELS = {
  AUTHORITY: "AUTHORITY CLAIM",
  ISOLATION: "ISOLATION",
  THREAT_URGENCY: "THREAT / URGENCY",
  FINANCIAL_DEMAND: "FINANCIAL DEMAND"
};

const scenarioSelect = document.getElementById("scenarioSelect");
const modeSelect = document.getElementById("modeSelect");
const startBtn = document.getElementById("startBtn");
const pauseBtn = document.getElementById("pauseBtn");
const endBtn = document.getElementById("endBtn");
const audioPlayBtn = document.getElementById("audioPlayBtn");
const audioMuteBtn = document.getElementById("audioMuteBtn");
const volumeControl = document.getElementById("volumeControl");
const volumeValue = document.getElementById("volumeValue");
const statusStrip = document.getElementById("statusStrip");
const modeBadge = document.getElementById("modeBadge");
const modeDetail = document.getElementById("modeDetail");
const callerIdEl = document.getElementById("callerId");
const callerStatusEl = document.getElementById("callerStatus");
const callTimerEl = document.getElementById("callTimer");
const callDurationEl = document.getElementById("callDuration");
const headerTimer = document.getElementById("headerTimer");
const headerLabel = document.getElementById("headerLabel");
const headerState = document.getElementById("headerState");
const audioStateEl = document.getElementById("audioState");
const sourceStateEl = document.getElementById("sourceState");
const waveformEl = document.getElementById("waveform");
const transcriptLines = document.getElementById("transcriptLines");
const scoreNum = document.getElementById("scoreNum");
const tierPill = document.getElementById("tierPill");
const scoreBar = document.getElementById("scoreBar");
const stageRows = document.querySelectorAll(".stage-row");
const pipelineSteps = document.querySelectorAll(".pipeline-step");
const criticalOverlay = document.getElementById("criticalOverlay");
const dismissAlert = document.getElementById("dismissAlert");
const criticalReason = document.getElementById("criticalReason");
const eventFeed = document.getElementById("eventFeed");
const callAudio = document.getElementById("callAudio");
const sttPipelineLabel = document.getElementById("pipelineSttText");

let scenarios = {};
let currentScenario = null;
let currentMode = null;
let preparedSegments = [];
let es = null;
let callRunning = false;
let audioCtx = null;
let analyser = null;
let sourceNode = null;
let freqData = null;
let bars = [];
let criticalShown = false;
let displayedEvents = new Set();
let pendingEvents = [];
let streamDone = false;
let waveformFrame = null;
let lastAudioError = "";

const NUM_BARS = 64;

function buildWaveform() {
  waveformEl.innerHTML = "";
  bars = [];
  for (let i = 0; i < NUM_BARS; i++) {
    const bar = document.createElement("i");
    bar.className = "wave-bar";
    waveformEl.appendChild(bar);
    bars.push(bar);
  }
}

function formatTime(sec) {
  sec = Math.max(0, Math.floor(Number(sec) || 0));
  return `${Math.floor(sec / 60).toString().padStart(2, "0")}:${(sec % 60).toString().padStart(2, "0")}`;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[c]));
}

function tierColor(tier) {
  return {
    LOW: "var(--low)",
    MEDIUM: "var(--medium)",
    HIGH: "var(--high)",
    CRITICAL: "var(--critical)"
  }[tier] || "var(--muted)";
}

function setPipeline(name, active) {
  const el = document.querySelector(`.pipeline-step[data-step="${name}"]`);
  if (el) el.classList.toggle("active", !!active);
}

function addFeed(label, text, tone = "") {
  const row = document.createElement("div");
  row.className = `feed-row ${tone}`;
  row.innerHTML = `<span>${escapeHtml(label)}</span><b>${escapeHtml(text)}</b>`;
  if (eventFeed.querySelector(".feed-empty")) eventFeed.innerHTML = "";
  eventFeed.prepend(row);
  while (eventFeed.children.length > 6) eventFeed.lastChild.remove();
}

function setHeader(state, critical = false) {
  headerLabel.textContent = state;
  headerState.className = `live-dot ${critical ? "critical" : state === "CALL ACTIVE" ? "active" : ""}`;
}

function resetUI() {
  criticalShown = false;
  displayedEvents.clear();
  pendingEvents = [];
  streamDone = false;
  lastAudioError = "";
  criticalOverlay.classList.remove("show");
  scoreNum.textContent = "0";
  scoreNum.style.color = "var(--muted)";
  scoreBar.style.width = "0%";
  scoreBar.style.color = "var(--low)";
  tierPill.textContent = "LOW";
  tierPill.className = "tier-pill LOW";
  const stageSummary = document.getElementById("stageSummary");
  if (stageSummary) stageSummary.textContent = "MONITORING FOR ESCALATION";
  stageRows.forEach(row => row.classList.remove("fired", "current"));
  pipelineSteps.forEach(step => step.classList.remove("active"));
  transcriptLines.innerHTML = `<div class="empty-state">Awaiting monitored speech…</div>`;
  eventFeed.innerHTML = `<div class="feed-empty">Backend events will appear here.</div>`;
  callTimerEl.textContent = "00:00";
  callDurationEl.textContent = "/ 00:00";
  headerTimer.textContent = "00:00";
  audioStateEl.textContent = "READY";
  sourceStateEl.textContent = "LOCAL WAV";
  modeBadge.textContent = "MODE — NOT STARTED";
  modeDetail.textContent = "Select a scenario and start a monitored demo.";
  statusStrip.className = "status-strip";
  statusStrip.innerHTML = `<span class="status-dot"></span><strong>SYSTEM READY</strong><span>Prototype processes local / recorded audio only.</span>`;
  setHeader("READY");
}

async function loadScenarios() {
  const res = await fetch(`${API_BASE}/api/scenarios`, { cache: "no-store" });
  if (!res.ok) throw new Error("Backend is not reachable.");
  const data = await res.json();
  scenarioSelect.innerHTML = "";
  scenarios = {};
  data.scenarios.forEach(s => {
    scenarios[s.id] = s;
    const option = document.createElement("option");
    option.value = s.id;
    option.textContent = s.label;
    scenarioSelect.appendChild(option);
  });
}

async function prepareScenario(id) {
  const requested = modeSelect.value;
  const res = await fetch(
    `${API_BASE}/api/demo/prepare/${encodeURIComponent(id)}?mode=${encodeURIComponent(requested)}`,
    { cache: "no-store" }
  );
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Unable to prepare demo.");
  return data;
}

async function setupAnalyser() {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    addFeed("AUDIO", "Web Audio analyser unavailable; playback remains active.");
    return;
  }
  try {
    if (!audioCtx) {
      audioCtx = new AudioContextClass();
      sourceNode = audioCtx.createMediaElementSource(callAudio);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.72;
      freqData = new Uint8Array(analyser.frequencyBinCount);
      sourceNode.connect(analyser);
      analyser.connect(audioCtx.destination);
    }
    if (audioCtx.state === "suspended") await audioCtx.resume();
  } catch (err) {
    console.warn("Audio analyser unavailable:", err);
    analyser = null;
    addFeed("AUDIO", "Waveform analyser unavailable; real WAV playback is unaffected.");
  }
}

function animateWaveform() {
  if (waveformFrame) cancelAnimationFrame(waveformFrame);

  const draw = () => {
    if (!callRunning) {
      bars.forEach(bar => { bar.style.height = "3px"; });
      waveformFrame = null;
      return;
    }

    if (analyser && !callAudio.paused && !callAudio.ended) {
      analyser.getByteFrequencyData(freqData);
      const step = Math.max(1, Math.floor(freqData.length / bars.length));
      bars.forEach((bar, i) => {
        const v = freqData[Math.min(freqData.length - 1, i * step)] || 0;
        bar.style.height = `${3 + (v / 255) * 70}px`;
      });
    } else {
      bars.forEach(bar => { bar.style.height = "3px"; });
    }

    waveformFrame = requestAnimationFrame(draw);
  };
  draw();
}

function updateClock() {
  const current = callAudio.currentTime || 0;
  callTimerEl.textContent = formatTime(current);
  headerTimer.textContent = formatTime(current);
  if (Number.isFinite(callAudio.duration)) {
    callDurationEl.textContent = `/ ${formatTime(callAudio.duration)}`;
  }
}

function revealTranscript(payload) {
  const key = Number(payload.line_index);
  if (displayedEvents.has(key)) return;
  displayedEvents.add(key);

  const empty = transcriptLines.querySelector(".empty-state");
  if (empty) empty.remove();

  transcriptLines.querySelectorAll(".transcript-entry.current")
    .forEach(x => x.classList.remove("current"));

  const entry = document.createElement("article");
  entry.className = `transcript-entry current ${payload.tier === "CRITICAL" ? "critical" : ""}`;
  entry.dataset.index = key;
  entry.innerHTML = `
    <div class="transcript-meta">
      <span>${formatTime(payload.start)}</span>
      <span class="speaker">${escapeHtml(payload.speaker || "CALLER")}</span>
      ${payload.matched_stage
        ? `<span class="detected">${escapeHtml(STAGE_LABELS[payload.matched_stage] || payload.matched_stage)}</span>`
        : ""}
    </div>
    <div class="transcript-text">${escapeHtml(payload.text)}</div>
  `;
  transcriptLines.appendChild(entry);
  transcriptLines.scrollTop = transcriptLines.scrollHeight;
}

function updateThreat(payload) {
  scoreNum.textContent = payload.score;
  scoreNum.style.color = tierColor(payload.tier);
  tierPill.textContent = payload.tier;
  tierPill.className = `tier-pill ${payload.tier}`;
  const activeStage = payload.matched_stage ? (STAGE_LABELS[payload.matched_stage] || payload.matched_stage) : "";
  const stageSummary = document.getElementById("stageSummary");
  if (stageSummary) stageSummary.textContent = activeStage ? `CURRENT SIGNAL: ${activeStage}` : "MONITORING FOR ESCALATION";
  scoreBar.style.color = tierColor(payload.tier);
  scoreBar.style.width = `${Math.min(100, Math.max(0, payload.score / (payload.max_possible || 110) * 100))}%`;

  stageRows.forEach(row => {
    const stage = row.dataset.stage;
    row.classList.toggle("fired", (payload.fired_stages || []).includes(stage));
    row.classList.toggle("current", payload.matched_stage === stage);
  });

  if (payload.matched_stage) {
    addFeed("STAGE", STAGE_LABELS[payload.matched_stage] || payload.matched_stage,
      payload.tier === "CRITICAL" ? "critical" : "");
  }
  addFeed("RISK", `${payload.score} · ${payload.tier}`);
}

function renderBackendEvent(payload) {
  setPipeline("input", true);
  setPipeline("stt", true);
  setPipeline("match", true);
  setPipeline("risk", true);
  revealTranscript(payload);
  updateThreat(payload);

  if (payload.tier === "HIGH" || payload.tier === "CRITICAL") {
    setPipeline("alert", true);
  }

  if (payload.tier === "CRITICAL" && !criticalShown) {
    criticalShown = true;
    criticalReason.textContent = payload.matched_stage === "FINANCIAL_DEMAND"
      ? "Financial demand detected after authority, isolation and threat escalation."
      : "Critical scam pattern detected by the Kavach risk engine.";
    criticalOverlay.classList.add("show");
    statusStrip.className = "status-strip critical";
    statusStrip.innerHTML = `<span class="status-dot"></span><strong>CRITICAL FRAUD PATTERN DETECTED</strong><span>Backend risk engine escalation</span>`;
    setHeader("CALL ACTIVE", true);
  }
}

function pumpAudioEvents() {
  if (currentMode === "fallback") return;
  const now = callAudio.currentTime || 0;
  pendingEvents.sort((a, b) => Number(a.start) - Number(b.start));
  while (pendingEvents.length && Number(pendingEvents[0].start) <= now + 0.04) {
    const payload = pendingEvents.shift();
    renderBackendEvent(payload);
  }
}

function handleSSE(payload) {
  if (currentMode === "fallback") {
    callTimerEl.textContent = formatTime(payload.elapsed);
    headerTimer.textContent = formatTime(payload.elapsed);
    if (payload.tier === "HIGH" || payload.tier === "CRITICAL") setPipeline("alert", true);
    renderBackendEvent(payload);
    return;
  }

  // Audio modes: SSE is data delivery only. HTML5 audio.currentTime controls
  // when the event becomes visible, so there is no second fake demo clock.
  pendingEvents.push(payload);
  pumpAudioEvents();
}

function connectStream() {
  if (es) {
    es.close();
    es = null;
  }

  const id = encodeURIComponent(currentScenario.id);
  // Always replay from the beginning on reconnect. The backend reconstructs
  // risk state server-side; the UI ignores events it already displayed.
  es = new EventSource(
    `${API_BASE}/api/stream/${id}?mode=${encodeURIComponent(currentMode)}&from=0&at=0`
  );

  es.onmessage = e => {
    try { handleSSE(JSON.parse(e.data)); }
    catch (err) { console.error("Invalid SSE payload", err); }
  };

  es.addEventListener("done", () => {
    streamDone = true;
    addFeed("SYSTEM", "Detection stream complete");
    setPipeline("alert", criticalShown);
  });

  es.onerror = () => {
    if (es && es.readyState === EventSource.CLOSED) return;
    if (callRunning && !callAudio.ended && currentMode !== "fallback") {
      addFeed("STREAM", "SSE disconnected; audio playback is unaffected.", "critical");
    }
  };
}

async function startDemo() {
  if (callRunning) return;
  currentScenario = scenarios[scenarioSelect.value];
  if (!currentScenario) return;

  resetUI();
  startBtn.disabled = true;
  scenarioSelect.disabled = true;
  modeSelect.disabled = true;
  endBtn.disabled = false;
  pauseBtn.disabled = false;
  audioPlayBtn.disabled = false;

  statusStrip.innerHTML = `<span class="status-dot"></span><strong>PREPARING</strong><span>Checking local WAV and transcript path…</span>`;
  setHeader("PREPARING");

  try {
    const prepared = await prepareScenario(currentScenario.id);
    currentMode = prepared.mode;
    preparedSegments = prepared.segments || [];

    modeBadge.textContent = prepared.mode_label;
    sourceStateEl.textContent = prepared.audio_available ? "LOCAL WAV" : "NO AUDIO";
    callerIdEl.textContent = currentScenario.caller_id;
    callerStatusEl.textContent = currentScenario.caller_status;

    if (currentMode === "whisper") {
      sttPipelineLabel.textContent = "Faster-Whisper STT";
      modeDetail.textContent = "Actual WAV → local Faster-Whisper timestamps → unchanged Kavach pipeline.";
    } else if (currentMode === "precomputed") {
      sttPipelineLabel.textContent = "Precomputed Transcript";
      modeDetail.textContent = "Actual WAV → checked-in timestamps → unchanged Kavach pipeline.";
    } else {
      sttPipelineLabel.textContent = "Script Replay";
      modeDetail.textContent = "No usable audio/STT path. Existing timing replay is active.";
    }

    if (prepared.warning) addFeed("MODE", prepared.warning, "critical");

    callAudio.src = currentScenario.audio_url;
    callAudio.volume = Number(volumeControl.value);
    callAudio.currentTime = 0;
    callAudio.load();

    if (currentMode === "fallback") {
      callRunning = true;
      audioStateEl.textContent = "NO AUDIO";
      statusStrip.className = "status-strip fallback";
      statusStrip.innerHTML = `<span class="status-dot"></span><strong>DEMO FALLBACK</strong><span>Timing/script replay · backend detection remains real</span>`;
      setHeader("DEMO FALLBACK");
      connectStream();
      animateWaveform();
      return;
    }

    callRunning = true;
    statusStrip.innerHTML = `<span class="status-dot"></span><strong>CALL ACTIVE</strong><span>WAV playback is the master clock for this controlled demo.</span>`;
    setHeader("CALL ACTIVE");

    await setupAnalyser();
    connectStream();

    try {
      await callAudio.play();
      pauseBtn.textContent = "Ⅱ PAUSE";
      audioPlayBtn.textContent = "Ⅱ PAUSE";
      audioStateEl.textContent = "PLAYING";
      addFeed("AUDIO", "Local WAV playback started");
    } catch (err) {
      lastAudioError = err.message || "Browser blocked playback.";
      audioStateEl.textContent = "CLICK PLAY";
      pauseBtn.textContent = "▶ RESUME";
      audioPlayBtn.textContent = "▶ PLAY";
      statusStrip.className = "status-strip fallback";
      statusStrip.innerHTML = `<span class="status-dot"></span><strong>PLAYBACK BLOCKED</strong><span>Click PLAY / RESUME to allow browser audio.</span>`;
      addFeed("AUDIO", "Browser requires a user gesture before playback.", "critical");
    }

    animateWaveform();
  } catch (err) {
    console.error(err);
    addFeed("ERROR", err.message, "critical");
    stopDemo();
  }
}

async function playAudio() {
  if (!callRunning || currentMode === "fallback") return;
  try {
    if (audioCtx && audioCtx.state === "suspended") await audioCtx.resume();
    await callAudio.play();
    pauseBtn.textContent = "Ⅱ PAUSE";
    audioPlayBtn.textContent = "Ⅱ PAUSE";
    audioStateEl.textContent = "PLAYING";
    statusStrip.className = "status-strip";
    statusStrip.innerHTML = `<span class="status-dot"></span><strong>CALL ACTIVE</strong><span>WAV playback is the master clock.</span>`;
  } catch (err) {
    addFeed("AUDIO", `Playback failed: ${err.message}`, "critical");
  }
}

function togglePause() {
  if (!callRunning || currentMode === "fallback") return;

  if (!callAudio.paused && !callAudio.ended) {
    callAudio.pause();
    pauseBtn.textContent = "▶ RESUME";
    audioPlayBtn.textContent = "▶ PLAY";
    audioStateEl.textContent = "PAUSED";
    addFeed("AUDIO", `Paused at ${formatTime(callAudio.currentTime)}`);
  } else {
    playAudio();
  }
}

function setVolume() {
  const value = Number(volumeControl.value);
  callAudio.volume = value;
  volumeValue.textContent = `${Math.round(value * 100)}%`;
  audioMuteBtn.textContent = value === 0 ? "🔇 UNMUTE" : "🔊 MUTE";
}

function toggleMute() {
  if (callAudio.muted || callAudio.volume === 0) {
    callAudio.muted = false;
    callAudio.volume = Number(volumeControl.value) || 1;
    if (callAudio.volume === 0) {
      volumeControl.value = "1";
      callAudio.volume = 1;
    }
    audioMuteBtn.textContent = "🔊 MUTE";
  } else {
    callAudio.muted = true;
    audioMuteBtn.textContent = "🔇 UNMUTE";
  }
}

function stopDemo() {
  if (es) {
    es.close();
    es = null;
  }
  callAudio.pause();
  callAudio.removeAttribute("src");
  callAudio.load();

  callRunning = false;
  currentMode = null;
  preparedSegments = [];
  pendingEvents = [];
  displayedEvents.clear();
  streamDone = false;

  startBtn.disabled = false;
  scenarioSelect.disabled = false;
  modeSelect.disabled = false;
  endBtn.disabled = true;
  pauseBtn.disabled = true;
  audioPlayBtn.disabled = true;
  pauseBtn.textContent = "Ⅱ PAUSE";
  audioPlayBtn.textContent = "▶ PLAY";
  audioStateEl.textContent = "STOPPED";
  setHeader("READY", false);

  bars.forEach(bar => { bar.style.height = "3px"; });
  resetUI();
}

callAudio.addEventListener("loadedmetadata", () => {
  if (Number.isFinite(callAudio.duration)) {
    callDurationEl.textContent = `/ ${formatTime(callAudio.duration)}`;
  }
});

callAudio.addEventListener("timeupdate", () => {
  if (!callRunning) return;
  updateClock();
  pumpAudioEvents();
});

callAudio.addEventListener("play", () => {
  if (!callRunning) return;
  audioStateEl.textContent = "PLAYING";
  pauseBtn.textContent = "Ⅱ PAUSE";
  audioPlayBtn.textContent = "Ⅱ PAUSE";
});

callAudio.addEventListener("pause", () => {
  if (!callRunning || callAudio.ended) return;
  audioStateEl.textContent = "PAUSED";
  pauseBtn.textContent = "▶ RESUME";
  audioPlayBtn.textContent = "▶ PLAY";
});

callAudio.addEventListener("error", () => {
  if (!callRunning) return;
  const code = callAudio.error ? callAudio.error.code : 0;
  const message = code === 4
    ? "WAV could not be decoded by the browser."
    : "WAV could not be loaded.";
  addFeed("AUDIO", message, "critical");
  audioStateEl.textContent = "AUDIO ERROR";
  statusStrip.className = "status-strip critical";
  statusStrip.innerHTML = `<span class="status-dot"></span><strong>AUDIO ERROR</strong><span>${escapeHtml(message)}</span>`;
});

callAudio.addEventListener("ended", () => {
  if (!callRunning) return;
  pumpAudioEvents();
  audioStateEl.textContent = "ENDED";
  pauseBtn.disabled = true;
  audioPlayBtn.textContent = "▶ PLAY";
  addFeed("AUDIO", "Local WAV playback complete");
  setHeader(criticalShown ? "CRITICAL" : "COMPLETE", criticalShown);
});

startBtn.addEventListener("click", startDemo);
endBtn.addEventListener("click", stopDemo);
pauseBtn.addEventListener("click", togglePause);
audioPlayBtn.addEventListener("click", () => {
  if (callAudio.paused) playAudio();
  else togglePause();
});
audioMuteBtn.addEventListener("click", toggleMute);
volumeControl.addEventListener("input", setVolume);
dismissAlert.addEventListener("click", () => criticalOverlay.classList.remove("show"));
scenarioSelect.addEventListener("change", () => {
  if (!callRunning) {
    callAudio.pause();
    callAudio.currentTime = 0;
    callAudio.removeAttribute("src");
    callAudio.load();
    resetUI();
    callTimerEl.textContent = "00:00";
    callDurationEl.textContent = "/ 00:00";
  }
});

window.addEventListener("beforeunload", () => {
  if (es) es.close();
  if (audioCtx) audioCtx.close();
});

buildWaveform();
setVolume();
resetUI();
loadScenarios().catch(err => {
  statusStrip.className = "status-strip critical";
  statusStrip.innerHTML = `<span class="status-dot"></span><strong>BACKEND OFFLINE</strong><span>${escapeHtml(err.message)}</span>`;
  setHeader("OFFLINE", true);
});
