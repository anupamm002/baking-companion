"use strict";
const $ = (id) => document.getElementById(id);

let currentId = null;

function show(view) {
  for (const v of ["library", "add", "review", "detail"])
    $("view-" + v).hidden = (v !== view);
}

function fmtDur(secs) {
  if (secs == null) return null;
  secs = Math.round(secs);
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
  return (h ? h + "h" : "") + (m ? m + "m" : "") || "0m";
}

function nodeDetailHtml(n) {
  let h = "";
  if (n.says) h += `<p class="says">🔊 ${n.says}</p>`;
  if (n.description) h += `<p>${n.description}</p>`;
  if (n.ingredients && n.ingredients.length)
    h += "<ul class='ing'>" + n.ingredients.map((i) =>
      `<li>${i.qty != null ? i.qty + (i.unit || "") + " — " : ""}${i.name}</li>`).join("") + "</ul>";
  const meta = [];
  if (n.temperature) meta.push("🌡 " + n.temperature);
  const dur = n.duration && fmtDur(n.duration.typical);
  if (dur) meta.push("⏱ ~" + dur);
  if (n.readiness_hint) meta.push("✓ ready when " + n.readiness_hint);
  if (meta.length) h += `<p class="meta">${meta.join(" · ")}</p>`;
  if (n.references && n.references.length)
    h += n.references.map((r) =>
      `<a class="ref" href="${r.url || r.path || "#"}" target="_blank">▶ ${r.caption || r.type}`
      + `${r.t_start ? " @" + r.t_start : ""}</a>`).join("");
  return h || "<p class='muted'>No extra details.</p>";
}

async function openView(id) {
  currentId = id;
  const r = await api("/api/recipes/" + encodeURIComponent(id));
  const rec = r.recipe;
  $("detailName").textContent = rec ? rec.name : id;
  $("detailMeta").textContent = rec
    ? `v${rec.version} · ${rec.nodes.length} steps`
      + (rec.equipment && rec.equipment.length ? " · " + rec.equipment.join(", ") : "")
    : "(could not parse)";
  const ol = $("detailSteps"); ol.innerHTML = "";
  for (const n of (rec ? rec.nodes : [])) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="steprow"><span class="chev">▸</span>`
      + `<span class="title">${n.title || n.id}</span></div>`
      + `<div class="detail" hidden>${nodeDetailHtml(n)}</div>`;
    const detail = li.querySelector(".detail"), chev = li.querySelector(".chev");
    const toggle = () => { detail.hidden = !detail.hidden; chev.textContent = detail.hidden ? "▸" : "▾"; };
    li.querySelector(".title").onclick = toggle; chev.onclick = toggle;
    ol.appendChild(li);
  }
  show("detail");
}
$("detailBack").onclick = loadLibrary;
$("detailEdit").onclick = () => openRecipe(currentId);

async function api(path, method, body) {
  const opt = { method: method || "GET" };
  if (body) { opt.headers = { "Content-Type": "application/json" }; opt.body = JSON.stringify(body); }
  return (await fetch(path, opt)).json();
}

// ---- library ----
async function loadLibrary() {
  const items = await api("/api/recipes");
  const ol = $("recipeList");
  ol.innerHTML = items.length ? "" : "<li>No recipes yet — add one.</li>";
  for (const r of items) {
    const li = document.createElement("li");
    const meta = r.error ? "<em>(invalid)</em>" : `· ${r.nodes} steps · v${r.version}`;
    li.innerHTML = `<span class="title">${r.name} ${meta}</span>`;
    const view = document.createElement("button");
    view.className = "tap"; view.textContent = "view";
    view.onclick = () => openView(r.id);
    const edit = document.createElement("button");
    edit.className = "tap"; edit.textContent = "edit";
    edit.onclick = () => openRecipe(r.id);
    const del = document.createElement("button");
    del.className = "tap"; del.textContent = "delete";
    del.onclick = async () => {
      if (confirm("Delete " + r.name + "?")) {
        await fetch("/api/recipes/" + encodeURIComponent(r.id), { method: "DELETE" });
        loadLibrary();
      }
    };
    li.append(view, edit, del);
    ol.appendChild(li);
  }
  show("library");
}

// ---- add ----
$("addBtn").onclick = () => {
  $("inUrl").value = ""; $("inText").value = ""; $("inImages").value = "";
  $("addStatus").textContent = "";
  show("add");
};
$("addCancel").onclick = loadLibrary;
$("reviewCancel").onclick = loadLibrary;

// Downscale to <=1500px JPEG so phone photos become small, fast requests.
function fileToB64(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const MAX = 1500;
      let { width, height } = img;
      if (width > MAX || height > MAX) {
        const s = MAX / Math.max(width, height);
        width = Math.round(width * s); height = Math.round(height * s);
      }
      const c = document.createElement("canvas");
      c.width = width; c.height = height;
      c.getContext("2d").drawImage(img, 0, 0, width, height);
      resolve({ mime: "image/jpeg", data: c.toDataURL("image/jpeg", 0.85).split(",")[1] });
    };
    img.onerror = reject;
    img.src = url;
  });
}

$("genBtn").onclick = async () => {
  const n = $("inImages").files.length;
  $("addStatus").textContent = "Thinking… building your recipe"
    + (n ? " (reading " + n + " photo" + (n > 1 ? "s" : "") + ", ~10–30s)" : "") + "…";
  try {
    const images = await Promise.all([...$("inImages").files].map(fileToB64));
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 150000);
    const r = await (await fetch("/api/recipes/import", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: $("inUrl").value.trim(), text: $("inText").value.trim(), images,
      }), signal: ctrl.signal,
    })).json();
    clearTimeout(timer);
    if (!r.ok) { $("addStatus").textContent = "Error: " + r.error; return; }
    openReview(r.yaml, r.recipe, r.questions);
  } catch (e) {
    $("addStatus").textContent = "Timed out or failed: " + e
      + ". Check the Termux window for errors, or try again.";
  }
};

// ---- review / edit ----
function openReview(yaml, recipe, questions) {
  $("yamlEditor").value = yaml;
  let s = recipe ? `${recipe.name} — ${recipe.nodes.length} steps` : "";
  if (questions && questions.length)
    s += " · Questions: " + questions.map((q) => q.replace(/^#\s*-\s*/, "")).join("; ");
  $("reviewSummary").textContent = s;
  $("reviewStatus").textContent = "";
  show("review");
}

async function openRecipe(id) {
  const r = await api("/api/recipes/" + encodeURIComponent(id));
  openReview(r.yaml, r.recipe, null);
}

$("aiEditBtn").onclick = async () => {
  const instr = $("aiInstr").value.trim();
  if (!instr) return;
  $("reviewStatus").textContent = "Applying edit…";
  const r = await api("/api/recipes/ai_edit", "POST",
    { yaml: $("yamlEditor").value, instruction: instr });
  if (!r.ok) { $("reviewStatus").textContent = "Error: " + r.error; return; }
  $("yamlEditor").value = r.yaml; $("aiInstr").value = "";
  $("reviewStatus").textContent = "Updated — review and Save.";
  if (r.recipe) $("reviewSummary").textContent = `${r.recipe.name} — ${r.recipe.nodes.length} steps`;
};

$("saveBtn").onclick = async () => {
  $("reviewStatus").textContent = "Saving…";
  const r = await api("/api/recipes/save", "POST", { yaml: $("yamlEditor").value });
  if (!r.ok) { $("reviewStatus").textContent = "Invalid recipe: " + r.error; return; }
  loadLibrary();
};

loadLibrary();
