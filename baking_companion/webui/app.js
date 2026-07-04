"use strict";
const $ = (id) => document.getElementById(id);
const ICON = { blocked: "·", ready: "○", active: "◉", done: "✓", skipped: "⤫" };
let listening = false, recog = null, frontier = [];
let state = null, mediaByNode = {}, firedTimers = new Set();

// ---- audio (shared context, resumed on any tap so the alarm can sound) ----
let audioCtx = null;
function ensureAudio() {
  if (!audioCtx) { try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (_) {} }
  if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
}
document.addEventListener("click", ensureAudio);

function speak(text) {
  if (!text || !window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text.replace(/\[.*?\]/g, ""));
  u.rate = 1.0; u.lang = "en-US";
  speechSynthesis.cancel(); speechSynthesis.speak(u);
}

function beep() {
  ensureAudio();
  if (!audioCtx) return;
  const g = audioCtx.createGain(); g.connect(audioCtx.destination);
  const o = audioCtx.createOscillator(); o.type = "sine"; o.frequency.value = 880;
  o.connect(g);
  const t = audioCtx.currentTime;
  for (let i = 0; i < 3; i++) {
    g.gain.setValueAtTime(0.0001, t + i * 0.45);
    g.gain.exponentialRampToValueAtTime(0.35, t + i * 0.45 + 0.05);
    g.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.45 + 0.35);
  }
  o.start(t); o.stop(t + 1.4);
}

function alarm(title) {
  beep();
  speak((title || "Timer") + " is done.");
  if (window.Notification && Notification.permission === "granted")
    new Notification("⏰ " + (title || "Timer") + " done");
  $("assistant").textContent = "⏰ " + (title || "Timer") + " — time's up!";
}

// ---- media (grouped per step) ----
async function loadMedia() {
  const items = await (await fetch("/api/media")).json();
  mediaByNode = {};
  for (const m of items) (mediaByNode[m.node] = mediaByNode[m.node] || []).push(m);
}
async function deleteMedia(id) {
  if (!confirm("Delete this capture?")) return;
  await fetch("/api/media/" + id, { method: "DELETE" });
  await loadMedia(); render();
}
function mediaStrip(nodeId) {
  const items = mediaByNode[nodeId] || [];
  if (!items.length) return "";
  return `<div class="stepmedia">` + items.map((m) =>
    `<span class="thumbwrap">`
    + `<a href="${m.url}" target="_blank">`
    + (m.kind === "video"
        ? `<video src="${m.url}" class="thumb" muted playsinline preload="metadata"></video><span class="playbadge">▶</span>`
        : `<img src="${m.url}" class="thumb" loading="lazy">`)
    + `</a><button class="delmedia" data-id="${m.id}">✕</button></span>`).join("") + `</div>`;
}

// ---- steps ----
function stepButtons(n) {
  if (n.status === "done" || n.status === "skipped")
    return `<button class="tap" data-cmd="reopen" data-node="${n.id}">undo</button>`;
  let b = "";
  if (n.status !== "active")
    b += `<button class="tap" data-cmd="begin" data-node="${n.id}">start</button>`;
  return b + `<button class="tap" data-cmd="done" data-node="${n.id}">done</button>`;
}
function stepDetail(n) {
  let h = "";
  if (n.says) h += `<p class="says">🔊 ${n.says}</p>`;
  if (n.description) h += `<p>${n.description}</p>`;
  if (n.ingredients && n.ingredients.length)
    h += "<ul class='ing'>" + n.ingredients.map((i) =>
      `<li>${i.qty != null ? i.qty + (i.unit || "") + " — " : ""}${i.name}</li>`).join("") + "</ul>";
  const meta = [];
  if (n.temperature) meta.push("🌡 " + n.temperature);
  if (n.duration) meta.push("⏱ ~" + n.duration);
  if (n.readiness) meta.push("✓ ready when " + n.readiness);
  if (meta.length) h += `<p class="meta">${meta.join(" · ")}</p>`;
  if (n.references && n.references.length)
    h += n.references.map((r) =>
      `<a class="ref" href="${r.url || r.path || "#"}" target="_blank">▶ ${r.caption || r.type}`
      + `${r.t_start ? " @" + r.t_start : ""}</a>`).join("");
  return h;
}

async function refresh() {
  state = await (await fetch("/api/state")).json();
  await loadMedia();
  render();
}

function render() {
  const s = state;
  if (!s || !s.bake) {
    $("bakeName").textContent = "No active bake";
    $("eta").textContent = "";
    $("assistant").textContent = "No bake in progress. Open 🍞 Bakes to start one.";
    $("steps").innerHTML = ""; $("alerts").innerHTML = ""; frontier = [];
    return;
  }
  $("bakeName").textContent = s.bake.name;
  $("eta").textContent = s.eta ? "done ~" + s.eta : "";
  frontier = s.frontier || [];
  $("alerts").innerHTML = (s.suggestions || [])
    .map((a) => `⏰ start <b>${a.node}</b> ~${a.when}`).join(" &nbsp; ");
  const ol = $("steps"); ol.innerHTML = "";
  for (const n of s.nodes) {
    const media = mediaByNode[n.id] || [];
    const li = document.createElement("li");
    li.className = n.status;
    const timer = n.ends_at
      ? `<span class="timer" data-ends="${n.ends_at}" data-title="${(n.title || n.id).replace(/"/g, "")}"></span>` : "";
    const badge = media.length ? `<span class="mediacount">📷${media.length}</span>` : "";
    li.innerHTML =
      `<div class="steprow"><span class="chev">▸</span>`
      + `<span class="icon">${ICON[n.status] || "?"}</span>`
      + `<span class="title">${n.title || n.id}</span>`
      + timer + badge
      + (n.finish ? `<span class="fin">~${n.finish}</span>` : "")
      + `<span class="stepbtns">${stepButtons(n)}</span></div>`
      + `<div class="detail" hidden>${stepDetail(n)}${mediaStrip(n.id)}</div>`;
    const detail = li.querySelector(".detail"), chev = li.querySelector(".chev");
    const toggle = () => { detail.hidden = !detail.hidden; chev.textContent = detail.hidden ? "▸" : "▾"; };
    li.querySelector(".title").onclick = toggle;
    chev.onclick = toggle;
    li.querySelectorAll("button[data-cmd]").forEach((b) =>
      b.onclick = (e) => { e.stopPropagation(); command(b.dataset.cmd, b.dataset.node); });
    li.querySelectorAll(".delmedia").forEach((b) =>
      b.onclick = (e) => { e.stopPropagation(); deleteMedia(b.dataset.id); });
    ol.appendChild(li);
  }
  updateTimers();
}

// ---- live countdown timers ----
function fmtRem(s) {
  const m = Math.floor(s / 60), ss = s % 60;
  return (m < 10 ? "0" : "") + m + ":" + (ss < 10 ? "0" : "") + ss;
}
function updateTimers() {
  const now = Date.now();
  document.querySelectorAll(".timer[data-ends]").forEach((el) => {
    const end = Date.parse(el.dataset.ends);
    if (isNaN(end)) { el.textContent = ""; return; }
    const rem = Math.round((end - now) / 1000);
    if (rem > 0) {
      el.textContent = "⏳ " + fmtRem(rem);
      el.classList.toggle("soon", rem <= 60);
    } else {
      el.textContent = "⏰ time's up";
      el.classList.add("done");
      const key = el.dataset.ends;
      if (!firedTimers.has(key)) { firedTimers.add(key); alarm(el.dataset.title); }
    }
  });
}
setInterval(updateTimers, 1000);

// ---- commands / ask ----
async function command(cmd, node) {
  if (cmd === "begin" && window.Notification && Notification.permission === "default")
    try { Notification.requestPermission(); } catch (_) {}
  const s = await (await fetch("/api/command", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cmd, node }),
  })).json();
  if (s.bake !== undefined) { state = s; render(); }
}
async function ask(text) {
  $("heard").textContent = "“" + text + "”";
  const r = await (await fetch("/api/ask", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  })).json();
  $("assistant").textContent = r.text;
  speak(r.text);
  if (r.state) { state = r.state; render(); }
  if (r.action === "capture") openCamera();
}

// ---- speech input ----
function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { $("assistant").textContent = "This browser has no Web Speech API — use Chrome."; return null; }
  const r = new SR();
  r.continuous = true; r.interimResults = false; r.lang = "en-US";
  r.onresult = (e) => {
    const t = e.results[e.results.length - 1][0].transcript.trim();
    if (t) ask(t);
  };
  r.onend = () => { if (listening) { try { r.start(); } catch (_) {} } };
  return r;
}
$("micBtn").onclick = () => {
  if (!recog) recog = initRecognition();
  if (!recog) return;
  listening = !listening;
  $("micBtn").classList.toggle("on", listening);
  $("micBtn").textContent = listening ? "⏹ Stop" : "🎙️ Start listening";
  if (listening) { try { recog.start(); } catch (_) {} speak("Listening."); }
  else recog.stop();
};

// ---- camera / photo / video ----
let stream = null, recorder = null, chunks = [];
function stopStream() {
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
}
async function openCamera() {
  stopStream();
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "environment",
        width: { ideal: 3840 }, height: { ideal: 2160 },
        advanced: [{ focusMode: "continuous" }],
      },
      audio: true,
    });
  } catch (e) {
    $("camWrap").hidden = false; $("camStatus").textContent = "Camera error: " + e;
    return;
  }
  const v = $("video");
  v.srcObject = stream;
  await v.play().catch(() => {});
  $("camWrap").hidden = false;
  $("camBtn").hidden = true;
  $("camStatus").textContent = "";
}
function closeCamera() {
  if (recorder && recorder.state === "recording") recorder.stop();
  stopStream();
  $("camWrap").hidden = true;
  $("camBtn").hidden = false;
}
$("camBtn").onclick = openCamera;
$("closeCamBtn").onclick = closeCamera;

async function uploadCapture(blob, type) {
  const node = frontier[0] || "";
  await fetch("/api/capture?node=" + encodeURIComponent(node), {
    method: "POST", headers: { "Content-Type": type }, body: blob,
  });
  await loadMedia(); render();
}

// High-res photo: prefer ImageCapture.takePhoto() (full sensor); fall back to a frame grab.
$("snapBtn").onclick = async () => {
  if (!stream) { $("camStatus").textContent = "Open the camera first."; return; }
  $("camStatus").textContent = "Capturing…";
  let blob = null, type = "image/jpeg";
  const track = stream.getVideoTracks()[0];
  if (window.ImageCapture) {
    try { const ic = new ImageCapture(track); blob = await ic.takePhoto(); type = blob.type || "image/jpeg"; }
    catch (_) { blob = null; }
  }
  if (!blob) {
    const v = $("video");
    if (!v.videoWidth) { $("camStatus").textContent = "Camera not ready yet…"; return; }
    const c = $("canvas"); c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.95));
  }
  await uploadCapture(blob, type);
  $("camStatus").textContent = "📸 Photo saved.";
};

function pickMime() {
  for (const m of ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm", "video/mp4"])
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m;
  return "";
}
$("recBtn").onclick = () => {
  if (recorder && recorder.state === "recording") { recorder.stop(); return; }
  if (!stream) { $("camStatus").textContent = "Open the camera first."; return; }
  chunks = [];
  recorder = new MediaRecorder(stream, pickMime() ? { mimeType: pickMime() } : undefined);
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = async () => {
    const type = recorder.mimeType || "video/webm";
    $("camStatus").textContent = "Uploading video…";
    await uploadCapture(new Blob(chunks, { type }), type);
    $("camStatus").textContent = "🎥 Video saved.";
    $("recBtn").textContent = "🎥 Record"; $("recBtn").classList.remove("on");
  };
  recorder.start();
  $("recBtn").textContent = "⏹ Stop"; $("recBtn").classList.add("on");
  $("camStatus").textContent = "● Recording…";
};

refresh();
setInterval(refresh, 15000);
