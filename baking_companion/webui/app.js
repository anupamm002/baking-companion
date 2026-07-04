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
    `<a href="${m.url}" target="_blank"><img src="${m.url}" loading="lazy"`
    + ` alt="${m.node || ""}" title="${m.node || ""} · ${m.ts || ""}"></a>`).join("");
}

// ---- state rendering ----
async function refresh() {
  const s = await (await fetch("/api/state")).json();
  render(s);
  loadMedia();
}
function render(s) {
  $("bakeName").textContent = s.bake.name;
  $("eta").textContent = s.eta ? "done ~" + s.eta : "";
  frontier = s.frontier || [];
  $("alerts").innerHTML = (s.suggestions || [])
    .map((a) => `⏰ start <b>${a.node}</b> ~${a.when}`).join(" &nbsp; ");
  const ol = $("steps"); ol.innerHTML = "";
  for (const n of s.nodes) {
    const li = document.createElement("li");
    li.className = n.status;
    const act = n.status === "ready" ? `<button class="tap" data-cmd="begin" data-node="${n.id}">start</button>`
      : n.status === "active" ? `<button class="tap" data-cmd="done" data-node="${n.id}">done</button>` : "";
    li.innerHTML = `<span class="icon">${ICON[n.status] || "?"}</span>`
      + `<span class="title">${n.title || n.id}</span>`
      + (n.finish ? `<span class="fin">~${n.finish}</span>` : "") + act;
    ol.appendChild(li);
  }
  ol.querySelectorAll("button[data-cmd]").forEach((b) =>
    b.onclick = () => command(b.dataset.cmd, b.dataset.node));
}

// ---- commands / ask ----
async function command(cmd, node) {
  const s = await (await fetch("/api/command", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cmd, node }),
  })).json();
  render(s);
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
  if (r.action === "capture") { openCamera(); }
}

// ---- speech input (Web Speech, continuous, auto-restart) ----
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

// ---- camera / capture ----
let stream = null;
async function openCamera() {
  $("camWrap").hidden = false; $("snapBtn").hidden = false;
  if (!stream) {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      $("video").srcObject = stream;
    } catch (e) { $("assistant").textContent = "Camera error: " + e; }
  }
}
$("camBtn").onclick = openCamera;
$("snapBtn").onclick = async () => {
  const v = $("video"), c = $("canvas");
  c.width = v.videoWidth; c.height = v.videoHeight;
  c.getContext("2d").drawImage(v, 0, 0);
  const blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.9));
  const node = frontier[0] || "";
  await fetch("/api/capture?node=" + encodeURIComponent(node), {
    method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob,
  });
  $("assistant").textContent = "Captured a photo for " + (node || "the bake") + ".";
  speak("Got it.");
  loadMedia();
};

refresh();
setInterval(refresh, 15000);
