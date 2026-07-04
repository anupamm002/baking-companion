# Baking Companion — Architecture

> Status: design draft. Reviewable notes; not yet implemented.

## Guiding principle: FSM orchestrates, LLM is a tool

Most agent apps are **LLM-as-orchestrator** — every turn hits the model, which
decides what tool to call. We invert this:

> **A local finite state machine (dialogue manager over the recipe graph) is the
> orchestrator. The cloud LLM is just one tool it can call — the "reasoning" tool —
> alongside `capture_photo`, `start_timer`, `check_time`, etc.**

This is a classic slot-filling dialogue manager over a state machine. Why it fits:

- **Fewer cloud touchpoints** — routine turns never leave the device.
- **Deterministic latency** for common actions (capture, timer, navigation).
- **No history to ship** — see context management below.
- **Graceful degradation** — without an API key you still get timers, capture,
  and navigation. Good for open-source users.

## Two-tier router

The **intent classifier** is the gate between tiers.

### Tier 0 — local, no LLM (target: ~80% of turns)

| Intent | Handling |
|---|---|
| `capture_photo` / `capture_video` | run tool, auto-tag from current state |
| `start_timer` / `cancel_timer` | local scheduler |
| `time_left?` / `what's next?` / `where am I?` | read runtime state |
| `mark_step_done` / `next` / `back` | advance FSM |
| `pause_bake` / `resume` | state transition |
| `add_note "kitchen feels cold"` | append to episodic log |

### Tier 1 — cloud LLM (genuine judgment only)

- "Does this look proofed?" (vision)
- "It's cold and rainy — should I extend bulk?" (reason over intent + conditions + past bakes)
- "Why was my crumb dense last time?" (memory synthesis)
- Recipe import from URL/photo
- Post-bake retrospective / lesson extraction

### Intent classifier — build order

1. **Rules + fuzzy matching first.** Vocabulary is tiny, domain-specific, command-like.
   Debuggable; doubles as the eval set later.
2. **Embedding-based classification** (sentence-transformers, on the brain not the Pi)
   only when the rules baseline hits a ceiling.
3. **Low-confidence → escalate to Tier 1** (or re-prompt). The LLM catches the long
   tail of phrasings and prevents misfired tools on bad transcripts.

## Context management — never send history; send a bundle

A bake spans days, so there is no meaningful "full history." Each Tier-1 call is
**stateless** and assembled locally:

```
context_bundle =
    current step's rationale + completion_condition      (from recipe template)
  + compact runtime snapshot (elapsed, conditions, recent deviations)
  + top-k retrieved lessons for (recipe, step, conditions) (from semantic memory)
  + the specific question (+ image if visual)
```

A few hundred tokens, no transcript. This is essentially **RAG over our own state +
memory**. Prompt-caching the static recipe rationale is a later optimization.

## Known weak link: STT

Tier-0 router quality depends on transcript quality in a noisy kitchen. Mitigations
that bias the design:

1. **Wake-word-gated short commands** (not open dictation) → short, classifiable utterances.
2. **Low-confidence transcripts** route to Tier-1 or a re-prompt rather than misfiring.
3. Decide early whether STT runs on the satellite or the brain (lean: brain).

## Off-the-shelf landscape (nothing does the whole thing)

- Baker's-percentage / formula tools (BreadBoss, calculators) — math only.
- Sourdough trackers (logging only, no reasoning).
- **Voice plumbing worth reusing:** Home Assistant + Wyoming (faster-whisper, Piper
  TTS, openWakeWord, Rhasspy). Same thin-satellite + central-brain pattern.
- Notifications: `ntfy.sh` (self-hostable push) or Pushover. Avoid WhatsApp.

## Storage & formats (two layers, don't conflate)

| Layer | Nature | Store |
|---|---|---|
| **Recipe templates** | static, human-authored, versioned, shareable | **YAML files** (readable, diffable, git/PR-friendly, easy to open-source) |
| **Bake instances + history + memory + media metadata** | mutable, growing, queried | **SQLite** (embedded, zero-server, single file, ships with Python — ideal on-phone/Termux) |

- **Pydantic models** are the single source of truth for the schema — validate, and
  serialize to/from both YAML (authoring) and SQLite (runtime). LLM importer emits YAML
  validated against them before acceptance.
- **No graph DB** (Neo4j etc.) — DAGs are tiny (tens of nodes); nodes/edges are rows/JSON,
  Python walks them. A graph DB would be an over-engineered dependency that hurts the
  "clone and run on a phone" story.
- **Media files** live on disk; SQLite rows hold tags + pointers.
- First reference recipe / test fixture: `recipes/country_loaf.yaml`.

## Phasing

1. **Text/CLI brain** — recipe schema + state machine + tagged capture. Proves the data model.
2. **Voice loop** — wake word + STT + TTS.
3. **Flexible-timing intelligence** — reason over step tolerances + spoken conditions.
4. **Vision** — "is it proofed?", starter rise checks.
5. **Memory + comparison** — bake history, lessons, side-by-side media. Optional display.
