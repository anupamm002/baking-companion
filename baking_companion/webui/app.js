"use strict";
/* Baking Companion — single-page app in the Modernist design system.
   Bottom tab bar switches Current / Bakes / Recipes; overlays (camera, lightbox,
   finish dialog) live in index.html and are toggled, not re-rendered. */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---- inline Lucide-style icons ----
const I = {
  mic: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"></rect><path d="M5 10a7 7 0 0 0 14 0"></path><line x1="12" y1="19" x2="12" y2="22"></line><line x1="8" y1="22" x2="16" y2="22"></line></svg>`,
  cam: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8a2 2 0 0 1 2-2h2l1.2-2h5.6L16 6h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"></path><circle cx="12" cy="13" r="3.5"></circle></svg>`,
  alarm: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="8"></circle><line x1="12" y1="13" x2="12" y2="9"></line><line x1="12" y1="13" x2="15" y2="15"></line><line x1="5" y1="3" x2="2" y2="6"></line><line x1="19" y1="3" x2="22" y2="6"></line></svg>`,
  plus: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>`,
  x: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="6" x2="18" y2="18"></line><line x1="18" y1="6" x2="6" y2="18"></line></svg>`,
  check: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-neutral-900)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 12 10 17 19 6"></polyline></svg>`,
  skip: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-neutral-500)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="6" x2="18" y2="18"></line><line x1="18" y1="6" x2="6" y2="18"></line></svg>`,
  temp: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="10" y="3" width="4" height="14" rx="2"></rect><circle cx="12" cy="18" r="3"></circle></svg>`,
  clock: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"></circle><line x1="12" y1="12" x2="12" y2="7"></line><line x1="12" y1="12" x2="16" y2="13.5"></line></svg>`,
  ready: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="5 12 10 17 19 6"></polyline></svg>`,
  speaker: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" stroke-width="2" style="flex:none;margin-top:2px"><path d="M11 5 6 9H2v6h4l5 4z"></path><path d="M15.5 8.5a5 5 0 0 1 0 7"></path></svg>`,
  media: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><path d="M21 16 15 10 5 21"></path></svg>`,
  play: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-bg)" stroke-width="2"><rect x="2" y="6" width="14" height="12" rx="2"></rect><path d="M16 10 22 6v12l-6-4z"></path></svg>`,
  photo: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-bg)" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><path d="M21 16 15 10 5 21"></path></svg>`,
  link: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="12" r="3"></circle><circle cx="16" cy="12" r="3"></circle><line x1="11" y1="12" x2="13" y2="12"></line></svg>`,
  eye: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"></path><circle cx="12" cy="12" r="3"></circle></svg>`,
  edit: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"></path></svg>`,
  trash: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"></path><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path></svg>`,
  sparkle: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8z"></path></svg>`,
  book: `<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-neutral-500)" stroke-width="1.5"><path d="M4 5a2 2 0 0 1 2-2h6v18H6a2 2 0 0 1-2-2z"></path><path d="M20 5a2 2 0 0 0-2-2h-6v18h6a2 2 0 0 0 2-2z"></path></svg>`,
};

// ---- app state ----
const App = {
  screen: "current",
  bakesScreen: "list",
  recipesScreen: "library",
  state: null,
  mediaByNode: {},
  expandedStepId: null,
  listening: false,
  heard: "",
  assistant: "Tap the mic and ask me anything.",
  quickTimer: null,        // { deadline }
  showQuickTimerForm: false,
  quickTimerMinutes: 5,
  firedTimers: new Set(),
  // recipes flow
  recipes: [],
  add: { url: "", text: "", images: [] },
  addStatus: "",
  review: { yaml: "", summary: "", status: "" },
  aiInstruction: "",
  detail: null,            // { name, meta, steps }
  detailExpandedStepId: null,
  // bakes flow
  bakes: [],
  newBakeRecipeId: "",
  newBakeName: "",
  newBakeStatus: "",
  cameraStepId: null,
};

// ---- api ----
async function api(path, method, body) {
  const opt = { method: method || "GET" };
  if (body) { opt.headers = { "Content-Type": "application/json" }; opt.body = JSON.stringify(body); }
  return (await fetch(path, opt)).json();
}

// ---- audio / speech out ----
let audioCtx = null;
function ensureAudio() {
  if (!audioCtx) { try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (_) {} }
  if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
}
document.addEventListener("click", ensureAudio);
function speak(text) {
  if (!text || !window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(String(text).replace(/\[.*?\]/g, ""));
  u.rate = 1.0; u.lang = "en-US";
  speechSynthesis.cancel(); speechSynthesis.speak(u);
}
function beep() {
  ensureAudio();
  if (!audioCtx) return;
  const g = audioCtx.createGain(); g.connect(audioCtx.destination);
  const o = audioCtx.createOscillator(); o.type = "sine"; o.frequency.value = 880; o.connect(g);
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
  App.assistant = "⏰ " + (title || "Timer") + " — time's up!";
  toast("⏰ " + (title || "Timer") + " — time's up!");
}

let toastTimer = null;
function toast(msg) {
  const el = $("toast");
  el.textContent = msg; el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}

// ---- time helpers ----
function mmss(sec) {
  if (sec <= 0) return "0:00";
  const m = Math.floor(sec / 60), s = sec % 60;
  return m + ":" + (s < 10 ? "0" : "") + s;
}
function remainingSec(iso) {
  const end = Date.parse(iso);
  if (isNaN(end)) return null;
  return Math.round((end - Date.now()) / 1000);
}

// ==================================================================== render
function render() {
  document.querySelectorAll(".tabbar button").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === App.screen));
  const area = $("screenArea");
  if (App.screen === "current") area.innerHTML = viewCurrent();
  else if (App.screen === "bakes") area.innerHTML = viewBakes();
  else area.innerHTML = viewRecipes();
  bind(area);
  updateTimers();
}

// ---- CURRENT ----
function subLabel(n) {
  if (n.status === "blocked") return n.finish ? "Blocked · finishes ~" + n.finish : "Blocked";
  if (n.status === "ready") return "Ready to start";
  if (n.status === "active") return n.readiness || "In progress";
  if (n.status === "done") return "Done";
  if (n.status === "skipped") return "Skipped";
  return "";
}
function stepButtonsHtml(n) {
  const term = n.status === "done" || n.status === "skipped";
  if (term) return `<button class="btn btn-secondary" data-cmd="reopen" data-node="${esc(n.id)}">Undo</button>`;
  let h = "";
  if (n.status !== "active") h += `<button class="btn btn-primary" data-cmd="begin" data-node="${esc(n.id)}">Start</button>`;
  h += `<button class="btn btn-primary" data-cmd="done" data-node="${esc(n.id)}">Done</button>`;
  return h;
}
function railHtml(n) {
  if (n.status === "done") return I.check;
  if (n.status === "skipped") return I.skip;
  if (n.status === "active") return `<span class="dot-active"></span>`;
  const stroke = n.status === "ready" ? "var(--color-accent)" : "var(--color-neutral-500)";
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${stroke}" stroke-width="2"><circle cx="12" cy="12" r="8"></circle></svg>`;
}
function timerSpanHtml(n, cls) {
  if (!n.ends_at) return "";
  return `<span class="${cls} timer-normal" data-ends="${esc(n.ends_at)}" data-title="${esc(n.title || n.id)}"></span>`;
}
function detailHtml(n) {
  const media = App.mediaByNode[n.id] || [];
  let h = `<div class="detail">`;
  if (n.says) h += `<div class="cue">${I.speaker}<p>${esc(n.says)}</p></div>`;
  if (n.description) h += `<p class="desc">${esc(n.description)}</p>`;
  if (n.ingredients && n.ingredients.length) {
    h += `<div><h6 class="kicker kicker-muted" style="margin:0 0 6px">Ingredients</h6>`;
    for (const i of n.ingredients)
      h += `<div class="ing-row"><span class="ing-qty">${esc(i.qty != null ? i.qty : "")} ${esc(i.unit || "")}</span>${esc(i.name)}</div>`;
    h += `</div>`;
  }
  const meta = [];
  if (n.temperature) meta.push(`<span>${I.temp}${esc(n.temperature)}</span>`);
  if (n.duration) meta.push(`<span>${I.clock}~${esc(n.duration)}</span>`);
  if (n.readiness) meta.push(`<span>${I.ready}${esc(n.readiness)}</span>`);
  if (meta.length) h += `<div class="meta-row">${meta.join("")}</div>`;
  for (const r of (n.references || [])) {
    const href = r.url || r.path || "#";
    const label = (r.caption || r.type || "reference") + (r.t_start ? " · " + r.t_start : "");
    h += `<a class="ref-link" href="${esc(href)}" target="_blank" rel="noopener">${I.link}${esc(label)}</a>`;
  }
  h += `<div><h6 class="kicker kicker-muted" style="margin:0 0 6px">Media</h6><div class="media-grid">`;
  if (media.length) for (const m of media) {
    const inner = m.kind === "video" ? `<video src="${esc(m.url)}" muted playsinline preload="metadata"></video>` + I.play
                                     : `<img src="${esc(m.url)}" loading="lazy">`;
    h += `<div class="thumb" data-open="${esc(m.url)}" data-kind="${esc(m.kind)}">${inner}`
       + `<button class="btn btn-icon del" data-del="${m.id}">${I.x}</button></div>`;
  } else h += `<p class="muted" style="margin:0;font-size:12px">No captures yet.</p>`;
  h += `</div></div></div>`;
  return h;
}
function heroHtml(n) {
  const term = n.status === "done" || n.status === "skipped";
  const canStart = !term && n.status !== "active";
  const canDone = !term;
  const meta = [];
  if (n.duration) meta.push(`<span>⏱ ~${esc(n.duration)}</span>`);
  if (n.readiness) meta.push(`<span>${esc(n.readiness)}</span>`);
  let acts = "";
  if (canStart) acts += `<button class="btn btn-primary" style="flex:1" data-cmd="begin" data-node="${esc(n.id)}">Start</button>`;
  if (canDone) acts += `<button class="btn btn-primary" style="flex:1" data-cmd="done" data-node="${esc(n.id)}">Done</button>`;
  acts += `<button class="btn btn-secondary" data-toggle="${esc(n.id)}">Details</button>`;
  const expanded = App.expandedStepId === n.id;
  return `<div class="hero">
    <div class="hero-top">
      <span class="tag tag-accent">${esc((n.status || "").toUpperCase())}</span>
      ${timerSpanHtml(n, "big-timer")}
    </div>
    <h3 data-toggle="${esc(n.id)}">${esc(n.title || n.id)}</h3>
    ${n.description ? `<p class="desc">${esc(n.description)}</p>` : ""}
    <div class="hero-meta">${meta.join("")}</div>
    <div class="hero-actions">${acts}</div>
    ${expanded ? detailHtml(n) : ""}
  </div>`;
}
function viewCurrent() {
  const s = App.state;
  if (!s || !s.bake) {
    return `<div class="empty">${I.book}<h4>No bake in progress</h4>
      <p>Open Bakes to start or resume one.</p>
      <button class="btn btn-primary" data-goto="bakes">Go to Bakes</button></div>`;
  }
  const nodes = s.nodes || [];
  const titleOf = {}; nodes.forEach((n) => (titleOf[n.id] = n.title || n.id));
  const doneCount = nodes.filter((n) => n.status === "done" || n.status === "skipped").length;
  const complete = nodes.length && doneCount === nodes.length;
  const hero = nodes.find((n) => n.status === "active") || nodes.find((n) => n.status === "ready");
  const listNodes = hero ? nodes.filter((n) => n.id !== hero.id) : nodes;

  let h = "";
  // header
  h += `<div class="topbar rule"><div>
      <h6 class="kicker kicker-muted" style="margin:0 0 4px">Current bake</h6>
      <h3>${esc(s.bake.name)}</h3></div>
      ${s.eta ? `<span class="tag tag-accent" style="white-space:nowrap;font-family:var(--font-heading);font-weight:800">done ~${esc(s.eta)}</span>` : ""}</div>`;
  // assistant
  h += `<div class="assistant-area rule">
      <div class="two-col"><span class="kicker kicker-accent">Assistant</span><p class="assistant-line">${esc(App.assistant)}</p></div>
      ${App.heard ? `<div class="two-col"><span class="kicker kicker-muted">Heard</span><p class="heard-line">"${esc(App.heard)}"</p></div>` : ""}</div>`;
  // controls
  h += `<div class="controls-row rule">
      <button class="btn btn-secondary mic-btn${App.listening ? " on" : ""}" id="micBtn">${I.mic} ${App.listening ? "Stop" : "Start listening"}</button>
      <button class="btn btn-secondary" id="openCam">${I.cam} Camera</button></div>`;
  // listening chips
  if (App.listening) {
    const chips = ["What's next?", "How long left?", "Does this look proofed?", "Extend bulk in cold weather?"];
    h += `<div class="chips rule">` + chips.map((c) =>
      `<button class="btn btn-secondary" data-ask="${esc(c)}">"${esc(c)}"</button>`).join("") + `</div>`;
  }
  // prep alerts
  if (s.suggestions && s.suggestions.length) {
    h += `<div class="prep-row rule">` + s.suggestions.map((a) =>
      `<div class="prep-pill">${I.alarm} Start ${esc(titleOf[a.node] || a.node)} ~${esc(a.when)}</div>`).join("") + `</div>`;
  }
  // quick timer
  h += `<div class="quick-row rule">`;
  if (App.quickTimer) {
    h += `<div class="quick-active"><span class="lbl">⧗ Quick timer — <span class="qt-timer" data-qt="1"></span></span>
        <button class="btn btn-icon" id="qtCancel" style="color:var(--color-bg);width:26px;height:26px">${I.x}</button></div>`;
  } else if (App.showQuickTimerForm) {
    h += `<div class="quick-form"><input class="input" type="number" min="1" max="180" id="qtMinutes" value="${App.quickTimerMinutes}">
        <span style="font-size:12px;opacity:.7">minutes</span>
        <button class="btn btn-primary" id="qtStart" style="font-size:12px;padding:6px 10px">Start</button>
        <button class="btn btn-ghost" id="qtClose" style="font-size:12px">Cancel</button></div>`;
  } else {
    h += `<button class="btn btn-ghost" id="qtOpen" style="font-size:12px">${I.plus} Quick timer (not tied to a step)</button>`;
  }
  h += `</div>`;
  // finish banner
  if (complete) {
    h += `<div class="finish-banner"><h4>Bake complete 🎉</h4>
        <p>Every step is done. Wrap it up with a shareable result card.</p>
        <button class="btn btn-primary" id="openFinish" style="align-self:flex-start">Finish &amp; share</button></div>`;
  }
  // steps
  h += `<div class="steps-head"><h6 class="kicker kicker-muted">Steps · ${doneCount}/${nodes.length}</h6></div>`;
  if (hero) h += heroHtml(hero);
  h += `<div class="steps">`;
  for (const n of listNodes) {
    const media = App.mediaByNode[n.id] || [];
    const expanded = App.expandedStepId === n.id;
    const op = (n.status === "done" || n.status === "skipped") ? ";opacity:.55" : "";
    h += `<div class="step"><div class="step-row" data-toggle="${esc(n.id)}" style="align-items:center${op}">
        <div class="step-rail">${railHtml(n)}</div>
        <div class="step-main"><div class="step-title-row"><span class="step-title">${esc(n.title || n.id)}</span>
          ${media.length ? `<span class="mediacount">${I.media}${media.length}</span>` : ""}</div>
          <div class="step-sub">${esc(subLabel(n))}</div></div>
        ${timerSpanHtml(n, "step-timer")}
        <div class="step-btns" data-stop="1">${stepButtonsHtml(n)}</div></div>
        ${expanded ? detailHtml(n) : ""}</div>`;
  }
  h += `</div>`;
  return h;
}

// ---- BAKES ----
function viewBakes() {
  if (App.bakesScreen === "new") {
    const opts = App.recipes.filter((r) => !r.error)
      .map((r) => `<option value="${esc(r.id)}"${r.id === App.newBakeRecipeId ? " selected" : ""}>${esc(r.name)}</option>`).join("");
    return `<div class="pad">
      <h3 style="margin:0 0 14px">Start a new bake</h3>
      <div class="field" style="margin-bottom:14px"><label>Recipe</label>
        <select class="input" id="newRecipe">${opts || `<option value="">No recipes — add one first</option>`}</select></div>
      <div class="field" style="margin-bottom:20px"><label>Name (optional)</label>
        <input class="input" id="newName" placeholder="e.g. Sunday loaf" value="${esc(App.newBakeName)}"></div>
      <div style="display:flex;gap:10px">
        <button class="btn btn-primary" style="flex:1" id="startBake">Start &amp; open</button>
        <button class="btn btn-secondary" id="cancelNew">Cancel</button></div>
      ${App.newBakeStatus ? `<p class="muted" style="margin-top:12px;font-size:13px">${esc(App.newBakeStatus)}</p>` : ""}</div>`;
  }
  let h = `<div class="pad">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <h3 style="margin:0">Bakes</h3>
      <button class="btn btn-primary" id="openNew">${I.plus} Start a bake</button></div>
    <div class="card-list">`;
  if (!App.bakes.length) h += `<p class="muted">No bakes yet — start one.</p>`;
  for (const b of App.bakes) {
    h += `<div class="card elev-sm selectable${b.current ? " current" : ""}" data-open-bake="${esc(b.id)}" data-current="${b.current ? 1 : 0}">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <span class="card-title">${esc(b.name)}</span>
        ${b.current ? `<span class="tag tag-accent">CURRENT</span>` : ""}</div>
      <p class="card-body" style="margin:0">${esc(b.recipe)}</p>
      <div class="card-meta"><span>${b.done}/${b.total} steps</span><span>·</span><span>${esc(b.status)}</span></div></div>`;
  }
  h += `</div></div>`;
  return h;
}

// ---- RECIPES ----
function viewRecipes() {
  const rs = App.recipesScreen;
  if (rs === "add") {
    return `<div class="pad">
      <h3 style="margin:0 0 14px">Add a recipe</h3>
      <div class="field" style="margin-bottom:12px"><label>URL</label>
        <input class="input" id="addUrl" placeholder="https://…" value="${esc(App.add.url)}"></div>
      <div class="field" style="margin-bottom:12px"><label>Paste or type text</label>
        <textarea class="input" id="addText" placeholder="Flour 500g, water 375g…">${esc(App.add.text)}</textarea></div>
      <div class="field" style="margin-bottom:18px"><label>Photos (${App.add.images.length})</label>
        <input type="file" id="addPhotos" accept="image/*" multiple></div>
      <div style="display:flex;gap:10px">
        <button class="btn btn-primary" style="flex:1" id="genBtn">${I.sparkle} Generate with AI</button>
        <button class="btn btn-secondary" id="cancelAdd">Cancel</button></div>
      ${App.addStatus ? `<p class="muted" style="margin-top:12px;font-size:13px">${esc(App.addStatus)}</p>` : ""}</div>`;
  }
  if (rs === "review") {
    return `<div class="pad">
      <h3 style="margin:0 0 14px">Review &amp; edit</h3>
      <div style="background:var(--color-surface);padding:12px;margin-bottom:14px;display:flex;gap:8px">
        <span class="card-kicker" style="flex:none">AI</span><p style="margin:0;font-size:13px">${esc(App.review.summary || "Review the recipe and save.")}</p></div>
      <div class="field" style="margin-bottom:14px"><label>Recipe (YAML)</label>
        <textarea class="input" id="draftYaml" style="min-height:220px;font-family:ui-monospace,monospace;font-size:12px">${esc(App.review.yaml)}</textarea></div>
      <div class="field" style="margin-bottom:18px"><label>AI-assisted edit</label>
        <div style="display:flex;gap:8px">
          <input class="input" id="aiInstr" placeholder="e.g. raise hydration to 80%, add a 20-min autolyse" value="${esc(App.aiInstruction)}">
          <button class="btn btn-secondary" style="flex:none" id="applyAi">Apply</button></div></div>
      <div style="display:flex;gap:10px">
        <button class="btn btn-primary" style="flex:1" id="saveRecipe">Save to library</button>
        <button class="btn btn-secondary" id="cancelReview">Cancel</button></div>
      ${App.review.status ? `<p class="muted" style="margin-top:12px;font-size:13px">${esc(App.review.status)}</p>` : ""}</div>`;
  }
  if (rs === "detail" && App.detail) {
    let h = `<div class="pad">
      <h3 style="margin:0">${esc(App.detail.name)}</h3>
      <p class="muted" style="margin:0 0 14px;font-size:12px">${esc(App.detail.meta)}</p>
      <div style="display:flex;flex-direction:column;margin-bottom:16px">`;
    App.detail.steps.forEach((st, i) => {
      const open = App.detailExpandedStepId === st.id;
      h += `<div class="detail-step"><div class="detail-step-row" data-dtoggle="${esc(st.id)}">
        <span class="detail-step-n">${i + 1}</span>
        <span class="detail-step-title">${esc(st.title)}</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="transform:rotate(${open ? 180 : 0}deg)"><polyline points="6 9 12 15 18 9"></polyline></svg></div>`;
      if (open) {
        const meta = [];
        if (st.duration) meta.push(`<span>⏱ ${esc(st.duration)}</span>`);
        if (st.readiness) meta.push(`<span>${esc(st.readiness)}</span>`);
        h += `<div style="padding:0 0 16px 32px;display:flex;flex-direction:column;gap:8px">
          ${st.description ? `<p style="margin:0;font-size:13px;opacity:.85">${esc(st.description)}</p>` : ""}
          ${meta.length ? `<div class="meta-row">${meta.join("")}</div>` : ""}</div>`;
      }
      h += `</div>`;
    });
    h += `</div><div style="display:flex;gap:10px">
      <button class="btn btn-primary" style="flex:1" id="editDetail">Edit</button>
      <button class="btn btn-secondary" id="backDetail">Back</button></div></div>`;
    return h;
  }
  // library
  let h = `<div class="pad">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <h3 style="margin:0">Recipes</h3>
      <button class="btn btn-primary" id="openAdd">${I.plus} Add recipe</button></div>
    <div class="card-list">`;
  if (!App.recipes.length) h += `<p class="muted">No recipes yet — add one.</p>`;
  for (const r of App.recipes) {
    const meta = r.error ? "invalid" : `${r.nodes} steps · v${r.version}`;
    h += `<div class="card elev-sm">
      <span class="card-kicker">Recipe</span>
      <span class="card-title">${esc(r.name)}</span>
      <p class="card-body" style="margin:0">${esc(meta)}</p>
      <div class="row-actions">
        <button class="btn btn-ghost" data-view="${esc(r.id)}">${I.eye}View</button>
        <button class="btn btn-ghost" data-edit="${esc(r.id)}">${I.edit}Edit</button>
        <button class="btn btn-ghost" style="color:var(--color-accent-700)" data-del-recipe="${esc(r.id)}">${I.trash}Delete</button></div></div>`;
  }
  h += `</div></div>`;
  return h;
}

// ==================================================================== timers
function updateTimers() {
  document.querySelectorAll("[data-ends]").forEach((el) => {
    const rem = remainingSec(el.dataset.ends);
    if (rem === null) { el.textContent = ""; return; }
    if (rem > 0) {
      el.textContent = "⏳ " + mmss(rem);
      el.classList.toggle("timer-urgent", rem <= 60);
      el.classList.toggle("timer-normal", rem > 60);
    } else {
      el.textContent = "⏰ time's up";
      el.classList.remove("timer-normal"); el.classList.add("timer-urgent");
      const key = el.dataset.ends;
      if (!App.firedTimers.has(key)) { App.firedTimers.add(key); alarm(el.dataset.title); }
    }
  });
  const qt = document.querySelector("[data-qt]");
  if (qt && App.quickTimer) {
    const rem = Math.round((App.quickTimer.deadline - Date.now()) / 1000);
    if (rem > 0) qt.textContent = mmss(rem);
    else {
      qt.textContent = "0:00";
      if (!App.firedTimers.has("qt")) { App.firedTimers.add("qt"); alarm("Quick timer"); }
      App.quickTimer = null; App.firedTimers.delete("qt");
      if (App.screen === "current") render();
    }
  }
}
setInterval(updateTimers, 1000);

// ==================================================================== actions
async function loadState() {
  App.state = await api("/api/state");
  const items = await api("/api/media");
  App.mediaByNode = {};
  for (const m of items) (App.mediaByNode[m.node] = App.mediaByNode[m.node] || []).push(m);
}
async function command(cmd, node) {
  if (cmd === "begin" && window.Notification && Notification.permission === "default")
    try { Notification.requestPermission(); } catch (_) {}
  App.state = await api("/api/command", "POST", { cmd, node });
  await loadStateMediaOnly();
  render();
}
async function loadStateMediaOnly() {
  const items = await api("/api/media");
  App.mediaByNode = {};
  for (const m of items) (App.mediaByNode[m.node] = App.mediaByNode[m.node] || []).push(m);
}
async function ask(text) {
  App.heard = text;
  App.assistant = "…";
  render();
  const r = await api("/api/ask", "POST", { text });
  App.assistant = r.text || "";
  speak(App.assistant);
  if (r.state) App.state = r.state;
  await loadStateMediaOnly();
  render();
  if (r.action === "capture") openCamera();
}

// ---- speech in ----
let recog = null;
function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { App.assistant = "This browser has no Web Speech API — use Chrome."; render(); return null; }
  const r = new SR();
  r.continuous = true; r.interimResults = false; r.lang = "en-US";
  r.onresult = (e) => { const t = e.results[e.results.length - 1][0].transcript.trim(); if (t) ask(t); };
  r.onend = () => { if (App.listening) { try { r.start(); } catch (_) {} } };
  return r;
}
function toggleListening() {
  if (!recog) recog = initRecognition();
  if (!recog) return;
  App.listening = !App.listening;
  if (App.listening) { try { recog.start(); } catch (_) {} speak("Listening."); }
  else recog.stop();
  render();
}

// ---- quick timer ----
function startQuickTimer() {
  const m = parseInt(($("qtMinutes") || {}).value || App.quickTimerMinutes, 10);
  if (!m || m < 1) return;
  App.quickTimer = { deadline: Date.now() + m * 60000 };
  App.firedTimers.delete("qt");
  App.showQuickTimerForm = false;
  if (window.Notification && Notification.permission === "default") try { Notification.requestPermission(); } catch (_) {}
  render();
}

// ---- camera ----
let stream = null, recorder = null, chunks = [];
function stopStream() { if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; } }
async function openCamera() {
  const s = App.state;
  App.cameraStepId = (s && s.frontier && s.frontier[0]) || null;
  const title = App.cameraStepId && s.nodes ? (s.nodes.find((n) => n.id === App.cameraStepId) || {}).title : null;
  $("camTarget").textContent = "Saving to: " + (title || "current step");
  $("camStatus").textContent = "";
  $("recIndicator").hidden = true;
  $("camera").hidden = false;
  stopStream();
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 3840 }, height: { ideal: 2160 }, advanced: [{ focusMode: "continuous" }] },
      audio: true,
    });
  } catch (e) { $("camStatus").textContent = "Camera error: " + e; return; }
  const v = $("video"); v.srcObject = stream; await v.play().catch(() => {});
}
function closeCamera() {
  if (recorder && recorder.state === "recording") recorder.stop();
  stopStream();
  $("camera").hidden = true;
}
async function uploadCapture(blob, type) {
  const node = App.cameraStepId || "";
  await fetch("/api/capture?node=" + encodeURIComponent(node), { method: "POST", headers: { "Content-Type": type }, body: blob });
  await loadStateMediaOnly();
  if (App.screen === "current") render();
}
async function snap() {
  if (!stream) { $("camStatus").textContent = "Camera not ready."; return; }
  $("camStatus").textContent = "Capturing…";
  let blob = null, type = "image/jpeg";
  const track = stream.getVideoTracks()[0];
  if (window.ImageCapture) { try { const ic = new ImageCapture(track); blob = await ic.takePhoto(); type = blob.type || "image/jpeg"; } catch (_) { blob = null; } }
  if (!blob) {
    const v = $("video");
    if (!v.videoWidth) { $("camStatus").textContent = "Camera not ready yet…"; return; }
    const c = $("canvas"); c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.95));
  }
  await uploadCapture(blob, type);
  $("camStatus").textContent = "📸 Photo saved.";
}
function pickMime() {
  for (const m of ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm", "video/mp4"])
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m;
  return "";
}
function toggleRecord() {
  if (recorder && recorder.state === "recording") { recorder.stop(); return; }
  if (!stream) { $("camStatus").textContent = "Camera not ready."; return; }
  chunks = [];
  recorder = new MediaRecorder(stream, pickMime() ? { mimeType: pickMime() } : undefined);
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = async () => {
    const type = recorder.mimeType || "video/webm";
    $("camStatus").textContent = "Uploading video…";
    await uploadCapture(new Blob(chunks, { type }), type);
    $("camStatus").textContent = "🎥 Video saved.";
    $("recIndicator").hidden = true;
  };
  recorder.start();
  $("recIndicator").hidden = false;
  $("camStatus").textContent = "● Recording…";
}

// ---- lightbox ----
function openLightbox(url, kind) {
  $("lightboxFrame").innerHTML = kind === "video"
    ? `<video src="${esc(url)}" controls autoplay playsinline></video>`
    : `<img src="${esc(url)}">`;
  $("lightbox").hidden = false;
}

// ---- media delete ----
async function deleteMedia(id) {
  if (!confirm("Delete this capture?")) return;
  await fetch("/api/media/" + id, { method: "DELETE" });
  await loadStateMediaOnly();
  render();
}

// ---- recipes flow ----
async function loadRecipes() { App.recipes = await api("/api/recipes"); }
function fileToB64(file) {
  return new Promise((resolve, reject) => {
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const MAX = 1500; let { width, height } = img;
      if (width > MAX || height > MAX) { const s = MAX / Math.max(width, height); width = Math.round(width * s); height = Math.round(height * s); }
      const c = document.createElement("canvas"); c.width = width; c.height = height;
      c.getContext("2d").drawImage(img, 0, 0, width, height);
      resolve({ mime: "image/jpeg", data: c.toDataURL("image/jpeg", 0.85).split(",")[1] });
    };
    img.onerror = reject; img.src = url;
  });
}
async function generateRecipe() {
  App.addStatus = "Thinking… building your recipe" + (App.add.images.length ? ` (reading ${App.add.images.length} photo${App.add.images.length > 1 ? "s" : ""}, ~10–30s)` : "") + "…";
  render();
  try {
    const r = await api("/api/recipes/import", "POST", { url: App.add.url.trim(), text: App.add.text.trim(), images: App.add.images });
    if (!r.ok) { App.addStatus = "Error: " + r.error; render(); return; }
    App.review = { yaml: r.yaml, status: "", summary: recipeSummary(r.recipe, r.questions) };
    App.aiInstruction = "";
    App.recipesScreen = "review"; render();
  } catch (e) { App.addStatus = "Failed: " + e; render(); }
}
function recipeSummary(recipe, questions) {
  let s = recipe ? `${recipe.name} — ${recipe.nodes.length} steps` : "";
  if (questions && questions.length) s += " · Questions: " + questions.map((q) => q.replace(/^#\s*-\s*/, "")).join("; ");
  return s;
}
async function applyAiEdit() {
  if (!App.aiInstruction.trim()) return;
  App.review.status = "Applying edit…"; render();
  const r = await api("/api/recipes/ai_edit", "POST", { yaml: App.review.yaml, instruction: App.aiInstruction });
  if (!r.ok) { App.review.status = "Error: " + r.error; render(); return; }
  App.review.yaml = r.yaml; App.aiInstruction = "";
  App.review.status = "Updated — review and Save.";
  if (r.recipe) App.review.summary = `${r.recipe.name} — ${r.recipe.nodes.length} steps`;
  render();
}
async function saveRecipe() {
  App.review.status = "Saving…"; render();
  const r = await api("/api/recipes/save", "POST", { yaml: App.review.yaml });
  if (!r.ok) { App.review.status = "Invalid recipe: " + r.error; render(); return; }
  await loadRecipes();
  App.recipesScreen = "library"; toast("Recipe saved."); render();
}
async function viewRecipeDetail(id) {
  const r = await api("/api/recipes/" + encodeURIComponent(id));
  const rec = r.recipe;
  App.detail = {
    name: rec ? rec.name : id,
    meta: rec ? `v${rec.version} · ${rec.nodes.length} steps` : "(could not parse)",
    steps: (rec ? rec.nodes : []).map((n) => ({
      id: n.id, title: n.title || n.id, description: n.description,
      duration: n.duration && n.duration.typical ? fmtDur(n.duration.typical) : null,
      readiness: n.readiness_hint,
    })),
  };
  App.detailRecipeId = id; App.detailExpandedStepId = null;
  App.recipesScreen = "detail"; render();
}
async function editRecipe(id) {
  const r = await api("/api/recipes/" + encodeURIComponent(id));
  App.review = { yaml: r.yaml, status: "", summary: recipeSummary(r.recipe, null) };
  App.aiInstruction = ""; App.recipesScreen = "review"; render();
}
async function deleteRecipe(id, name) {
  if (!confirm("Delete " + name + "?")) return;
  await fetch("/api/recipes/" + encodeURIComponent(id), { method: "DELETE" });
  await loadRecipes(); toast("Recipe deleted."); render();
}
function fmtDur(secs) {
  if (secs == null) return null;
  secs = Math.round(secs);
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
  return (h ? h + "h" : "") + (m ? m + "m" : "") || "0m";
}

// ---- bakes flow ----
async function loadBakes() { App.bakes = await api("/api/bakes"); }
async function startNewBake() {
  const rid = ($("newRecipe") || {}).value;
  if (!rid) { App.newBakeStatus = "Add a recipe first."; render(); return; }
  App.newBakeStatus = "Starting…"; render();
  const r = await api("/api/bakes", "POST", { recipe_id: rid, name: App.newBakeName.trim() });
  if (!r.ok) { App.newBakeStatus = "Error: " + r.error; render(); return; }
  App.bakesScreen = "list";
  await goTo("current");
}
async function switchBake(id, isCurrent) {
  if (!isCurrent) await api("/api/bakes/select", "POST", { bake_id: id });
  await goTo("current");
}

// ==================================================================== nav
async function goTo(screen) {
  App.screen = screen;
  if (screen === "current") { await loadState(); }
  else if (screen === "bakes") { await Promise.all([loadBakes(), loadRecipes()]); App.bakesScreen = "list"; }
  else if (screen === "recipes") { await loadRecipes(); App.recipesScreen = "library"; }
  render();
}

// ==================================================================== binding
function bind(area) {
  // tab bar bound once in init
  // toggles / commands via delegation
  area.querySelectorAll("[data-toggle]").forEach((el) => el.onclick = (e) => {
    if (e.target.closest("[data-stop]") || e.target.closest("[data-cmd]")) return;
    const id = el.dataset.toggle;
    App.expandedStepId = App.expandedStepId === id ? null : id; render();
  });
  area.querySelectorAll("[data-cmd]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); command(b.dataset.cmd, b.dataset.node); });
  area.querySelectorAll("[data-ask]").forEach((b) => b.onclick = () => ask(b.dataset.ask));
  area.querySelectorAll("[data-goto]").forEach((b) => b.onclick = () => goTo(b.dataset.goto));
  area.querySelectorAll("[data-open]").forEach((el) => el.onclick = (e) => {
    if (e.target.closest("[data-del]")) return; openLightbox(el.dataset.open, el.dataset.kind);
  });
  area.querySelectorAll("[data-del]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); deleteMedia(b.dataset.del); });

  const on = (id, ev, fn) => { const el = $(id); if (el) el[ev] = fn; };
  // current
  on("micBtn", "onclick", toggleListening);
  on("openCam", "onclick", openCamera);
  on("qtOpen", "onclick", () => { App.showQuickTimerForm = true; render(); });
  on("qtClose", "onclick", () => { App.showQuickTimerForm = false; render(); });
  on("qtStart", "onclick", startQuickTimer);
  on("qtMinutes", "oninput", (e) => { App.quickTimerMinutes = e.target.value; });
  on("qtCancel", "onclick", () => { App.quickTimer = null; render(); });
  on("openFinish", "onclick", () => { $("finishName").textContent = App.state.bake.name; $("finishDialog").hidden = false; });

  // bakes
  on("openNew", "onclick", () => { App.bakesScreen = "new"; App.newBakeStatus = ""; if (!App.newBakeRecipeId && App.recipes[0]) App.newBakeRecipeId = App.recipes[0].id; render(); });
  on("cancelNew", "onclick", () => { App.bakesScreen = "list"; render(); });
  on("startBake", "onclick", startNewBake);
  on("newRecipe", "onchange", (e) => { App.newBakeRecipeId = e.target.value; });
  on("newName", "oninput", (e) => { App.newBakeName = e.target.value; });
  area.querySelectorAll("[data-open-bake]").forEach((el) => el.onclick = () => switchBake(el.dataset.openBake, el.dataset.current === "1"));

  // recipes
  on("openAdd", "onclick", () => { App.add = { url: "", text: "", images: [] }; App.addStatus = ""; App.recipesScreen = "add"; render(); });
  on("cancelAdd", "onclick", () => { App.recipesScreen = "library"; render(); });
  on("addUrl", "oninput", (e) => { App.add.url = e.target.value; });
  on("addText", "oninput", (e) => { App.add.text = e.target.value; });
  on("addPhotos", "onchange", async (e) => {
    App.addStatus = "Reading photos…"; render();
    try { App.add.images = await Promise.all([...e.target.files].map(fileToB64)); App.addStatus = App.add.images.length + " photo(s) ready."; }
    catch (err) { App.addStatus = "Photo error: " + err; }
    render();
  });
  on("genBtn", "onclick", generateRecipe);
  on("draftYaml", "oninput", (e) => { App.review.yaml = e.target.value; });
  on("aiInstr", "oninput", (e) => { App.aiInstruction = e.target.value; });
  on("applyAi", "onclick", applyAiEdit);
  on("saveRecipe", "onclick", saveRecipe);
  on("cancelReview", "onclick", () => { App.recipesScreen = "library"; render(); });
  on("editDetail", "onclick", () => editRecipe(App.detailRecipeId));
  on("backDetail", "onclick", () => { App.recipesScreen = "library"; render(); });
  area.querySelectorAll("[data-view]").forEach((b) => b.onclick = () => viewRecipeDetail(b.dataset.view));
  area.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => editRecipe(b.dataset.edit));
  area.querySelectorAll("[data-del-recipe]").forEach((b) => b.onclick = () => {
    const r = App.recipes.find((x) => x.id === b.dataset.delRecipe) || {}; deleteRecipe(b.dataset.delRecipe, r.name || b.dataset.delRecipe);
  });
  area.querySelectorAll("[data-dtoggle]").forEach((el) => el.onclick = () => {
    App.detailExpandedStepId = App.detailExpandedStepId === el.dataset.dtoggle ? null : el.dataset.dtoggle; render();
  });
}

// ==================================================================== init
document.querySelectorAll(".tabbar button").forEach((b) => b.onclick = () => goTo(b.dataset.tab));
$("camClose").onclick = closeCamera;
$("camSnap").onclick = snap;
$("camRecord").onclick = toggleRecord;
$("lightbox").onclick = () => { $("lightbox").hidden = true; $("lightboxFrame").innerHTML = ""; };
$("finishClose").onclick = () => { $("finishDialog").hidden = true; };
$("finishShare").onclick = () => { $("finishDialog").hidden = true; toast("Shareable artifact coming soon."); };

// initial screen from path (deep links /bakes /recipes still work)
const path = location.pathname;
const initial = path.startsWith("/bakes") ? "bakes" : path.startsWith("/recipes") ? "recipes" : "current";
goTo(initial);

// poll live state while on the Current screen (skip while the camera is open)
setInterval(async () => {
  if (App.screen === "current" && $("camera").hidden) { await loadState(); render(); }
}, 15000);
