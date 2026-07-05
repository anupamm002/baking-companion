# Baking Companion — Project Status (snapshot 2026-07-05)

Read this first to pick the project back up. Design detail is in `01-architecture.md`,
`02-graph-model.md`, `03-hardware.md`; this file is "where things stand + how to run + what's next".

## What it is

A hands-free-capable, graph-driven **baking companion** for long bakes (sourdough loaf,
focaccia, pizza). Three core jobs: (1) never look up the recipe mid-bake, (2) effortless
timers, (3) effortless photo/video journaling — plus history/comparison later. Built to run
**on a spare Android phone** (Termux + the phone's Chrome), open-sourced at
**https://github.com/anupamm002/baking-companion** (public).

## Core architecture (unchanged, working)

- **FSM orchestrates, the LLM is one tool.** A local finite-state-machine dialogue manager
  runs the show; the cloud LLM is called only for reasoning (Tier-1). Inversion of the
  usual "LLM calls tools".
- **Two-tier router.** Tier-0 = local, rules+fuzzy intent classifier (`intents.py`),
  handles ~80% (status/next/time/show/begin/done/capture/note/when). Tier-1 = cloud LLM via
  the user's **OpenRouter** key, for judgment (why/does-this-look/is-it-ready), recipe
  import, etc. Low-confidence or judgment cues escalate.
- **Graph model.** Recipe = DAG (START→END, acyclic, loops flattened, AND-joins). Runtime
  bake = a **marking/frontier** (node status blocked/ready/active/done/skipped), advances
  **only on user confirmation**. Timer engine = a **live scheduler** over the DAG: forward
  ETAs + backward prep alerts (feed levain / preheat). Node time on nodes (`duration`),
  cross-branch scheduling on edges (`constraint`).
- **Ingredients** absolute-first (baker's % is an optional re-anchor lens). **Instances are
  editable overlays** on a versioned recipe snapshot. Material divide → **fork** into
  independent child instances (helper exists; UI not yet).
- **Storage.** Recipe templates = YAML files (`~/.baking_companion/recipes/`, seeded from
  bundled `recipes/`). Everything mutable = **SQLite** (`~/.baking_companion/baking.db`).
  Media files on disk under `media/<bake_id>/`. **No pydantic** (removed — schema is stdlib
  `dataclasses`); **only third-party dep is pyyaml**. LLM client = stdlib `urllib`; web
  server = stdlib `http.server`. Deliberately dependency-light so it installs on a phone
  with no compiling.

## Package map (`baking_companion/`)

`duration.py` (parse/format), `models.py` (dataclass schema + from_dict/to_dict),
`graph.py` (DAG utils), `recipe_loader.py`, `store.py` (SQLite), `engine.py` (marking,
confirm-only advance, capture, fork, reopen), `scheduler.py` (forward/backward),
`intents.py` + `router.py` (Tier-0/Tier-1), `llm.py` (OpenRouter), `importer.py`
(URL/text/photo → validated YAML, AI-edit), `library.py` (recipe library),
`web.py` (stdlib server), `webui/` (index/manage/bakes .html + app/manage/bakes .js + css),
`cli.py`. Tests in `tests/` (26 passing). First recipe: `recipes/country_loaf.yaml`.

## How to run

**Laptop (dev):**
```bash
cd ~/work/ideas/baking_companion
pip install -e .                 # gives the `bake` command (NOT `bc` — collides with the calculator)
export OPENROUTER_API_KEY=sk-or-...          # for Tier-1 / import
export BAKING_LLM_MODEL=anthropic/claude-sonnet-4.6
bake ping                        # verify key
bake serve                       # http://localhost:8765
# or: python3 -m baking_companion <cmd>   (no install needed)
```

**Phone (Termux):**
```bash
pkg install python git
git clone https://github.com/anupamm002/baking-companion.git && cd baking-companion
pip install -e .                 # pulls only pyyaml
# add key+model exports to ~/.bashrc, then: source ~/.bashrc
bake serve                       # open http://localhost:8765 in Chrome (localhost = secure context)
```
The browser does STT (Web Speech), TTS (speechSynthesis), camera (getUserMedia +
ImageCapture); Termux runs the Python brain. Only the phone is needed in the kitchen.

## CLI commands

`start`, `list`, `use`, `status`, `show`, `begin [--at --expect]`, `done`, `skip`,
`capture`, `note`, `when`, `timeline`, `ask "<q>"`, `import <src> [--dry-run]`, `ping`,
`serve`.

## UI (three linked screens)

- **/** live bake: expandable steps (ingredients/temp/duration/readiness/refs), per-step
  **start/done/undo**, **live countdown timers + alarm**, 📷 photo (hi-res via ImageCapture)
  + 🎥 video, **per-step media with delete**, optional voice. "No active bake" state.
- **/bakes**: list instances (progress), start a new bake from a library recipe, switch.
- **/recipes**: library (view/edit/delete), add via URL+text+photos → AI → validated YAML,
  review + AI-assisted edit, save.

## Known issues / caveats (TODO)

- **Timers** only show for steps that have a `duration`; no manual "quick timer" yet.
- **Phone push for timers** when the app is backgrounded is NOT done (only in-page
  beep/speak/Notification while screen on). Plan: ntfy.
- **Two parallel bakes** implemented but not yet user-verified end-to-end.
- **Voice** is manual start/stop; no wake word / local VAD; ~5s mic warmup at record start;
  voice "take a picture" opens the camera but doesn't auto-snap.
- **Video codec** support varies on Android Chrome (webm/mp4 fallback in place).
- **Recipe editor** is raw YAML (fine for owner; non-programmer form editor later).
- **Tier-1 context** bundle is thin (frontier + recent events); doesn't yet resolve the
  target node's full detail or retrieve past-bake lessons.

## Prioritized next steps

1. Phone push notifications (ntfy) for timers when backgrounded; manual quick-timer button.
2. Verify/patch two parallel bakes.
3. Voice-UX pass: wake word + local VAD gating, auto-snap on voice capture, warm the mic,
   auto-select a better TTS voice. Start **logging utterances** (future intent model).
4. Enrich Tier-1 context (target-node detail + retrieved memory).
5. Delight layer: cross-bake memory/lessons + side-by-side comparison.
6. Friendlier non-YAML recipe editor.

## Business direction (parked)

Hosted SaaS for hobby bakers is a real opportunity; keep an **open-core** split so the same
engine runs locally and server-side. Details in memory `proj-bc-roadmap`.
