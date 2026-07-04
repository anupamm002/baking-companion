# Baking Companion

A graph-driven, confirm-only assistant for long bakes (sourdough, focaccia, pizza).
Recipes are DAGs; a live bake is a *marking* over that graph; the timer engine is a
scheduler that plans forward (ETAs) and backward (when to feed the levain, start the
preheat). See `docs/` for the full design.

**Status:** Phase 1 — the CLI brain (schema, state machine, media tagging, scheduler).
Voice + phone (Termux + local web UI) come in later phases.

## Requirements

Python ≥ 3.10, `pydantic>=2`, `pyyaml>=6`. Data lives in `~/.baking_companion/`
(override with `BAKING_HOME`).

## Run

```bash
# from the repo root, no install needed:
python3 -m baking_companion <command>

# or install the `bake` entry point:
pip install -e .
bake <command>
```

## Commands

```
bake start <recipe>         create a bake (recipe = ./recipes/<id>.yaml or a path)
bake list                   list bakes
bake use <bake_id>          set the current bake
bake status                 marking + frontier
bake show <node>            full recipe detail for a step (+ past media across bakes)
bake begin <node> [--at T] [--expect 4h30m]
bake done <node> [--at T]
bake skip <node> [--reason ...]
bake capture <node> <file> [--tags a,b] [--caption ...]
bake note <node> <text...>
bake when                   levain-ready, next steps, ETA, prep alerts (preheat/score)
bake timeline               event log
bake ask "<question>"       natural language: routed Tier-0 (local) or Tier-1 (LLM)
bake import <url|photo|txt> [--dry-run]   LLM-assisted recipe import -> validated YAML
bake serve [--host H --port P]            phone web UI + voice backend (localhost)
```

## Voice / phone (Termux)

`bake serve` runs a stdlib HTTP server (no FastAPI/uvicorn) and, on the phone, you open
`http://localhost:8765` in Chrome. The browser does STT (`webkitSpeechRecognition`),
TTS (`speechSynthesis`) and camera (`getUserMedia`); the Python backend runs the
FSM/router/scheduler. Served over `localhost` = secure context, so no HTTPS needed.

## Cloud reasoning

Tier-1 (`bake ask` judgment questions, `bake import`) uses your **OpenRouter** key:

```bash
export OPENROUTER_API_KEY=sk-or-...
export BAKING_LLM_MODEL=anthropic/claude-sonnet-4.6   # optional
```

Without a key, Tier-0 still works fully; Tier-1 questions show the context bundle that
*would* be sent, and `bake import --dry-run` prints the exact prompt.

## Example (a country loaf)

```bash
bake start country_loaf --name "Sat loaf"
bake begin feed_levain --expect 4h30m
bake capture feed_levain ~/photos/starter.jpg --tags fed,1:1:1
bake when                       # -> levain ready ~11:37, prep alerts back-scheduled
bake done feed_levain           # when it peaks; downstream steps become 'ready'
bake begin autolyse
...
```

State advances **only** on your confirmation (`begin`/`done`); timers and readiness
hints are advisory. Timing drift (45 min instead of 30) just re-flows the schedule.
