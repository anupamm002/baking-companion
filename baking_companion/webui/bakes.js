"use strict";
const $ = (id) => document.getElementById(id);

function show(view) {
  $("view-list").hidden = view !== "list";
  $("view-new").hidden = view !== "new";
}

async function api(path, method, body) {
  const opt = { method: method || "GET" };
  if (body) { opt.headers = { "Content-Type": "application/json" }; opt.body = JSON.stringify(body); }
  return (await fetch(path, opt)).json();
}

async function loadBakes() {
  const items = await api("/api/bakes");
  const ol = $("bakeList");
  ol.innerHTML = items.length ? "" : "<li>No bakes yet — start one.</li>";
  for (const b of items) {
    const li = document.createElement("li");
    if (b.current) li.className = "active";
    const prog = b.total ? `${b.done}/${b.total} steps` : "";
    li.innerHTML = `<span class="title">${b.name}`
      + `<br><span class="fin">${b.recipe} · ${prog} · ${b.status}`
      + `${b.current ? " · current" : ""}</span></span>`;
    const open = document.createElement("button");
    open.className = "tap"; open.textContent = b.current ? "open" : "switch";
    open.onclick = async () => {
      if (!b.current) await api("/api/bakes/select", "POST", { bake_id: b.id });
      location.href = "/";
    };
    li.appendChild(open);
    ol.appendChild(li);
  }
  show("list");
}

$("newBtn").onclick = async () => {
  const recipes = await api("/api/recipes");
  const sel = $("recipeSel");
  sel.innerHTML = recipes.filter((r) => !r.error)
    .map((r) => `<option value="${r.id}">${r.name}</option>`).join("");
  $("bakeName").value = "";
  $("newStatus").textContent = "";
  show("new");
};
$("newCancel").onclick = loadBakes;

$("startBtn").onclick = async () => {
  const recipe_id = $("recipeSel").value;
  if (!recipe_id) { $("newStatus").textContent = "Add a recipe first."; return; }
  $("newStatus").textContent = "Starting…";
  const r = await api("/api/bakes", "POST", { recipe_id, name: $("bakeName").value.trim() });
  if (!r.ok) { $("newStatus").textContent = "Error: " + r.error; return; }
  location.href = "/";   // open the live view on the new bake
};

loadBakes();
