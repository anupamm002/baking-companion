"use strict";
const $ = (id) => document.getElementById(id);
const ICON = { blocked: "·", ready: "○", active: "◉", done: "✓", skipped: "⤫" };
let listening = false, recog = null, frontier = [];

// ---- speech output ----
function speak(text) {
  if (!text || !window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text.replace(/\[.*?\]/g, ""));
  u.rate = 1.0; u.lang = "en-US";
  speechSynthesis.cancel(); speechSynthesis.speak(u);
}

// ---- captures gallery ----
async function loadMedia() {
  const items = await (await fetch("/api/media")).json();
  const g = $("gallery");
  if (!items.length) { g.innerHTML = ""; return; }
  g.innerHTML = "<h2>Captures</h2>" + items.slice().reverse().map((m) =>
    `<a href="${m.url}" target="_blank" class="thumbwrap">`
    + (m.kind === "video"
        ? `<video src="${m.url}" class="thumb" muted playsinline preload="metadata"></video><span class="playbadge">▶</span>`
        : `<img src="${m.url}" class="thumb" loading="lazy" alt="${m.node || ""}">`)
    + `</a>`).join("");
}

// ---- state rendering ----
async function refresh() {
  const s = await (await fetch("/api/state")).json();
  render(s);
  loadMedia();
}

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
  return h || "<p class='muted'>No extra details.</p>";
}

function render(s) {
  if (!s.bake) {
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
    const li = document.createElement("li");
    li.className = n.status;
    li.innerHTML =
      `<div class="steprow">`
      + `<span class="chev">▸</span>`
      + `<span class="icon">${ICON[n.status] || "?"}</span>`
      + `<span class="title">${n.title || n.id}</span>`
      + (n.finish ? `<span class="fin">~${n.finish}</span>` : "")
      + `<span class="stepbtns">${stepButtons(n)}</span>`
      + `</div>`
      + `<div class="detail" hidden>${stepDetail(n)}</div>`;
    const detail = li.querySelector(".detail");
    const chev = li.querySelector(".chev");
    const toggle = () => {
      detail.hidden = !detail.hidden;
      chev.textContent = detail.hidden ? "▸" : "▾";
    };
    li.querySelector(".title").onclick = toggle;
    chev.onclick = toggle;
    li.querySelectorAll("button[data-cmd]").forEach((b) =>
      b.onclick = (e) => { e.stopPropagation(); command(b.dataset.cmd, b.dataset.node); });
    ol.appendChild(li);
  }
}

// ---- commands / ask ----
async function command(cmd, node) {
  const s = await (await fetch("/api/command", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cmd, node }),
  })).json();
  if (s.bake !== undefined) render(s);
}
async function ask(text) {
  $("heard").textContent = "“" + text + "”";
  const r = await (await fetch("/api/ask", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  })).json();
  $("assistant").textContent = r.text;
  speak(r.text);
  if (r.state) render(r.state);
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

// ---- camera / photo / video (fresh stream each open; preview always live) ----
let stream = null, recorder = null, chunks = [];

function stopStream() {
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
}

async function openCamera() {
  stopStream();                                  // avoid stale/frozen streams
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
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
}

$("snapBtn").onclick = async () => {
  const v = $("video");
  if (!v.videoWidth) { $("camStatus").textContent = "Camera not ready yet…"; return; }
  const c = $("canvas");
  c.width = v.videoWidth; c.height = v.videoHeight;
  c.getContext("2d").drawImage(v, 0, 0);
  const blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.92));
  await uploadCapture(blob, "image/jpeg");
  $("camStatus").textContent = "📸 Photo saved."; loadMedia();
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
    loadMedia();
  };
  recorder.start();
  $("recBtn").textContent = "⏹ Stop"; $("recBtn").classList.add("on");
  $("camStatus").textContent = "● Recording…";
};

refresh();
setInterval(refresh, 15000);
