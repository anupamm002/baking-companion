# Baking Companion — Build Plan (personal → public)

> Status: **plan, 2026-07-18.** How we get from the current local single-user app to a
> public PWA — without throwaway work and without ever losing the ability to bake with it.
> Supersedes the sequencing notes in `04-status.md` "next steps" and the memory roadmap.

## The premise (why this isn't a rewrite)

We are **already building the web version.** Because the browser does all I/O
(`getUserMedia`, Web Speech, `MediaRecorder`) and Python is only the brain behind an HTTP
API, the current app *is* the hosted-PWA architecture. **Termux is just today's host, not a
design.** So the path is additive layers, not a port:

| Already portable (value + novelty) | Additive later (not rework) |
|---|---|
| FSM engine, graph, scheduler, Tier-0/Tier-1 router, import, comparisons, reasoning | Auth + multi-user (single-user = 1 row) |
| Browser PWA (camera/mic/voice/timelapse), shareable artifact (ffmpeg.wasm) | SQLite → Postgres/Turso (storage layer only) |
| Web Push (works local *and* hosted) | Hosted HTTPS + PWA install polish, public signup |

## Two invariants that govern every phase

1. **Local single-user mode stays first-class the whole way.** `user_id` defaults to a
   `local` user and **auth is bypassable when running locally**, so building the hosted path
   never takes the baking tool away from you. You keep baking on every commit.
2. **The backend owns state and timers, always.** State + due timers must fire even when no
   browser is connected (phone locked/tab closed). This is already true in spirit (Python is
   authoritative); we make it literal with a server-side timer loop + Web Push.

## The design decisions this plan bakes in

- **Storage goes behind one interface.** `store.py` is nearly there — promote it to a
  `Store` protocol; SQLite is impl #1, Postgres/Turso is impl #2 later. **The recipe library
  moves behind the same interface** (YAML text stored as a column, not loose files) — keeps
  YAML as the format/source-of-truth while gaining per-user scoping and versioning (the
  "compare my v3 vs v4 bakes" feature wants versioned recipe rows anyway).
- **`user_id` is added to the schema now**, while there's one user. Every table
  (`bakes`, `node_states`, `events`, `media`, `recipes`) gets it; every query filters by it.
  Multi-tenancy then becomes wiring, not a migration.
- **Current-bake pointer moves from `current_bake.txt` into the store** (per-user), because a
  file pointer is single-tenant and doesn't survive multiple users / instances.
- **Auth is outsourced** (Supabase Auth: Google + magic link). Backend never handles
  passwords — it just validates the Supabase JWT and reads `user_id` from it.
- **HTTPS via a reverse proxy** (Caddy = auto-Let's-Encrypt in front of the stdlib server),
  which restores the secure context that localhost gave for free.
- **First production DB = SQLite on a VPS volume** (you're the only user → zero migration to
  get live). Swap to Postgres/Turso at the moment you open signups. The interface makes this
  a config change, not a rewrite.

---

## Phase 0 — Personal polish + web-target guardrails  *(local, keep baking)*

Goal: the app you *want to use for every bake* — aesthetic and fully functional — plus the
cheap-now structural seeds that stop future throwaway. Still runs on Termux/laptop.

**0a. UX/aesthetic pass** (own punch-list — audit separately):
- visual polish (typography, spacing, color, the empty/active/done states);
- the known rough edges: manual quick-timer button, timers for steps without a `duration`,
  voice "take a picture" should auto-snap, mic warmup, better TTS voice selection.

**0b. Storage interface + `user_id`** (contained refactor, high payoff):
- extract a `Store` protocol; keep `SqliteStore` as the impl;
- add `user_id` column to every table, default `local`; thread it through all queries;
- move recipe library into the store (YAML-text rows, per-user, versioned);
- replace `current_bake.txt` with a per-user current-bake row.

**0c. PWA-ify** (identical local & hosted):
- `manifest.webmanifest` + icons + `<meta>` tags → installable "Add to Home Screen";
- a service worker for the app shell (offline-tolerant UI, install lifecycle).

**0d. Server-owned timers + Web Push** (the real "backend as source of truth" piece):
- VAPID keys + a `push_subscriptions` table; client subscribes via the service worker;
- a server timer loop that checks due timers and sends Web Push — **fires with the tab
  closed / phone locked**, which the in-page beep never could. Works from localhost too.

*Exit:* you're baking on a nicer app that already installs like a native app and pushes
timer alerts to your lock screen — and the schema/persistence is multi-user-shaped.

## Phase 1 — Multi-user + auth  *(still runnable locally with auth off)*

- Supabase project; Supabase Auth (Google OAuth + email magic link) on the frontend.
- Backend validates the Supabase JWT (JWKS), extracts `user_id`, scopes every request.
  In `local` mode, a flag injects the `local` user and skips validation.
- Remove global singletons: resolve store/engine per-request per user (Phase 0b made state
  per-user already, so this is wiring).
- Seed each new user with the bundled starter recipes.

*Exit:* the same app serves N users; you still run it locally single-user for daily baking.

## Phase 2 — Hosting  *(become user #1 in production)*

- **Backend** on a small always-on VPS (Hetzner CX-class / Fly), running the engine + timer
  loop. ~₹500–700/mo.
- **HTTPS** via Caddy reverse proxy + a domain (~₹1000/yr) → camera/mic/Web Push all work.
- **DB**: SQLite on a persistent volume to start (you're the only user); Supabase for Auth.
- **Static PWA**: same server or Cloudflare Pages (free).
- **Media**: local disk on the VPS initially; Cloudflare R2 when it grows.

*Exit:* you bake on the hosted URL from your phone; this is now the staging that hardens the
product. Nothing about your daily use is local-only anymore.

## Phase 3 — Public launch readiness  *(flip the switch when it's genuinely good)*

- Onboarding + first-run flow; **prominent "Add to Home Screen"** (iOS Web Push needs an
  installed PWA, 16.4+).
- Free-tier limits (e.g. import cap) per the productization notes.
- **Privacy policy + delete-my-data** (required before public).
- The **shareable artifact** (timelapse + result card, ffmpeg.wasm client-side) = the growth
  loop; subtle watermark.
- Swap SQLite → Postgres/Turso the moment concurrency matters (interface swap).
- Landing page.

## Cross-cutting: the novelty / delight layer (the fun part, deployment-agnostic)

Cross-bake comparisons, richer Tier-1 reasoning/guidance with retrieved memory, the
shareable video/image generation. All portable — slot them in anytime, ideally on the live
product so you enjoy building them against real bakes. **Specialised CV/image-processing
models are explicitly parked (way future)** — when they return, the likely shape is a
home-GPU worker the cloud calls, to keep the always-on cost within budget.

**Temperature-adjusted fermentation timing — OPTIONAL, deferred, NOT an ML project.**
Rise's signature feature (see positioning below) recalculates bulk/proof times from dough
temperature. Do *not* frame this as a learned model — a personal app has near-zero labeled
bakes, fermentation is high-dimensional/noisy (flour, starter strength, hydration, salt),
and it genuinely needs baker domain knowledge. The pragmatic form is to encode **one
published baker heuristic** (fermentation rate ≈ doubles per ~8–10 °C, a Q10 rule of thumb)
as an *optional multiplier* on the existing `duration` ranges: user enters dough temp, the
scheduler shifts the ETA. It slots into a scheduler that already re-flows on actuals. Not
needed for the personal version; revisit only if wanted. (A per-baker learned refinement is
possible *far* later once real logged history exists — but only as a "someday," not a plan.)

## Competitive positioning (vs Rise — the benchmark)

Detailed scan 2026-07-18. Rise (iOS-only, subscription) is the serious incumbent and already
owns the **table-stakes layer**: AI recipe import, start-to-finish forward schedule with
per-step notifications, temperature-adjusted fermentation, and the usual calculators (DDT,
hydration, rise-time), starter reminders, photo journaling, sharing. **So do not headline
"scheduling + import"** — that's parity, not a moat.

Lead instead with what Rise structurally *cannot* do without a rewrite:
- **Cross-platform (Android / PWA)** — Rise is iOS-only; it can't even run on the target device.
- **Concurrent multi-bake** — Rise is explicitly one recipe at a time; the marking/frontier
  model gives parallel bakes for free.
- **Backward prep-alert scheduling** — a real Rise user complaint is the *inability to pick an
  end time and be told when to start*; the bidirectional scheduler (feed-levain/preheat
  back-alerts) is the crown jewel.
- **Graph/branching + resource scheduling** — Rise is a linear list; the DAG does parallel
  branches, forking, oven-conflict flags.
- **Hands-free voice copilot** — Rise is entirely tap-driven.
- **Auto shareable timelapse/result artifact** — the growth loop; Rise does photos, not the
  generated share-out.
- **Free & open.** Rise's existence = market validation, not a kill shot; different lane.
Contestable Rise weak spots: notification reliability (a reviewer missed feed alarms), rigid
units (no sub-½-tsp). The one genuine Rise lead worth matching = temperature-adjusted
fermentation (see the optional heuristic above).

## Suggested order of attack

Phase 0 is the meaty, satisfying part and it makes your own baking better immediately, so do
it first and in the 0a→0d order above. 0b (storage + `user_id`) is the single highest-leverage
task — it's what turns everything after it from "migration" into "wiring." Then 1 → 2 whenever
you want to be live; 3 only when you decide to open the doors. The delight layer threads
through wherever it's most fun.

**Public is explicitly optional.** The near-term intent (2026-07-18) is a *great version for
yourself*; going public is "if I feel like it, later." Phase 0 is 100% personal-use value.
Phases 1–3 add nothing you'd have to undo — the `user_id`/storage-interface/PWA/Web-Push
guardrails in Phase 0 are worth doing for the personal app on their own merits and *also*
happen to make public a bolt-on. So there is no fork to agonize over: build Phase 0 for you,
decide on public whenever (or never).
