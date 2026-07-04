# Baking Companion — The Graph (core data model)

> Status: **converging (2026-07-03).** Agreed model below; a few open forks at the end.
> This multi-attribute graph is the **core**; everything else (timers, media tagging,
> memory, comparison, queries) derives from it.

Three layers, kept strictly separate: **Recipe** (static template), **Bake** (runtime
instance), **Memory** (past instances + summaries).

## Structure (agreed)

- **DAG**: directed, acyclic, single `START` → single `END`.
- **Loops are flattened** (3 folds → `fold_1`, `fold_2`, `fold_3`). Flattening is a
  feature: each becomes its own trackable state with its own timer/media/deviation and a
  **stable `node_id`** → cross-bake comparison ("fold 2 across my last 5 bakes") is a
  one-line query.
- **Branches allowed, both directions**: joins (levain + flour+water → dough) and splits
  (parallel preheat; or dividing dough into loaf + focaccia).
- **Nodes = logical steps.** Ingredients / qty / temperature / method are **attributes**,
  not nodes.
- **Litmus test for "is it a node?"** — it's a node iff it has its own **time footprint**
  or needs its own **notification**; otherwise it's an attribute. (Encodes the
  "no micro-nodes" rule; answers the sub-recipe question: levain = node, "add 2 g salt"
  = attribute.)

## 1. Recipe = template

```yaml
node:
  id: bulk_fold_2
  type: action            # prep | mix | wait | action | bake | capture | subrecipe
  description: "Coil fold #2, then rest."
  ingredients: []         # attributes, not nodes
  temperature: null
  method: "Coil fold: lift from underneath, let it stretch, tuck."
  duration: { min: 20m, typical: 30m, max: 60m }   # INTRINSIC time of the step
  readiness_hint: "dough relaxed, ~30% risen, jiggly"   # advisory only (see below)
  nudge_after: typical                                  # when to send a soft prompt
  refs:
    videos: [ {url, t: "12:30"} ]        # timestamped
    photos_from_memory: []               # exemplars pulled from past instances
  capture: { prompt_photo: true, tags: [stage:bulk, fold:2] }
  says: "Time for fold 2. Give it a coil fold."

edge:
  from: preheat
  to: bake
  # EDGE time = cross-branch SCHEDULING offset, NOT "the wait":
  constraint: { kind: finish_by, target: bake_start }   # e.g. preheat done before bake
  # other kinds: start_before(target, lead), no_earlier_than
```

**Time split (resolves node-vs-edge question):**
- `node.duration` = how long the step occupies (active "knead 10–15" OR passive "bulk 4h"
  / "rest 30 between folds"). The between-folds gap is the fold node's own duration — no
  edge time needed for it.
- `edge` carries **scheduling constraints** (lead/lag) only, to coordinate parallel/prep
  branches (preheat, pull-banneton, levain).

## 2. Bake = runtime instance (a *marking*, not a pointer)

Runtime state = a **marking** over the graph. Every node has
`status ∈ {blocked, ready, active, done, skipped}`. A node becomes `ready` when all
predecessors are `done`; the "current state" is the **frontier** = ready ∪ active nodes.
This gives parallel branches for free, and concurrent bakes = two independent markings.

**State advances ONLY on user confirmation.** Timers, `nudge_after`, and photos are
**advisory** — they prompt, they never transition. This makes timing drift a non-event.

```yaml
bake:
  id: bake_2026_07_02_country
  recipe: country_loaf_v3
  status: active
  marking: { levain: done, mix: done, bulk_fold_2: active, preheat: blocked, ... }
  timestamps: { bulk_fold_2.started: 2026-07-02T14:05 }
  deviations: [ { node: bulk_fold_1, planned: 30m, actual: 47m, note: "cold kitchen" } ]
  conditions: { ambient_temp: 19C, weather: rainy }
  media: [ { file, node: bulk_fold_1, t, elapsed_in_node, tags } ]
  discussions: [ ... runtime Q&A / assumptions attached to nodes ... ]
```

## 3. Scheduler over the DAG (the timer/notify engine — crown jewel)

Recomputed **live** from the current marking + timestamps, in two directions:

- **Forward** — sum durations along paths → ETA to END, "next fold in 22 min."
- **Backward** — from a target node, subtract `edge` lead times → "feed levain now"
  (mix needs ripe levain ~7h out), "start preheat now" (bake needs hot oven in 45 min),
  "pull banneton in 5 min." Levain and preheat are the **same back-scheduling mechanism**.

Because state moves only on confirmation and durations are ranges, taking 45 min instead
of 30 just **re-flows** every downstream ETA and prep alert. "45 is fine" is the default
behavior, not a special case.

## Memory

- **Working** = active bake markings. **Episodic** = past bake instances (completed
  markings + media/timings/deviations). **Semantic** = LLM-distilled summaries/lessons.
- Everything keyed by `(recipe_id, node_id)` → template nodes can surface exemplar media
  from past instances; side-by-side comparison is a straight query.

## Query tiering

- **Structural / deterministic → Tier 0, no LLM**: what's next, what's left, ETA,
  ingredients/temperature for a step, total flour, when to start prep.
- **Open / why / visual → Tier 1**: "why was the crumb dense?", "does this look ready?".
Context sent to Tier 1 = current frontier + neighbor nodes + retrieved lessons + the
question (+ image). Never transcript history.

## Recipe import flow

LLM ingests URL/image/text → extracts steps → **expands loops** → **infers durations,
parallelism (preheat!), and lead times** → asks clarifying questions → emits the DAG
(YAML) for user review. Parallelism/lead-time inference is where the clarifying-questions
step earns its keep.

## Decisions (forks resolved 2026-07-03)

- **a) AND-only** join/split semantics (a node fires when all predecessors done). XOR/
  optional/conditional edges deferred until a real need appears.
- **b) Material divide → fork into independent instances.** See "Forking" below.
- **c) Movable anchor**, default = "I'm starting at X" (forward-schedule from a start
  time; backward-compute prep alerts relative to their target nodes).

## Forking (material divide)

- The **divide node** completes on the parent, then **spawns N child instances**, each
  with `derived_from: parent@divide` and inheriting pre-divide history **by reference**
  (shared mix/bulk shown in each child's history; nothing duplicated).
- Each child runs its **own subgraph**, either:
  1. a **branch of the same recipe**, or
  2. **grafted into a different recipe** (pizza) at a mid-graph **entry point** — a node
     flagged with a precondition (e.g. `requires: proofed_dough`); pizza's earlier
     dough-prep nodes are marked `satisfied_by_parent` / skipped.
- **MVP:** same-recipe branches. Design the **entry-point** concept now so cross-recipe
  grafting drops in later.
- Two live instances **compete for shared resources** (oven, fridge, counter, the baker's
  hands) → resource-constrained scheduling. The scheduler should **flag conflicts**
  ("oven busy until 7:10; pizza wants it at 7:00"). Optimization deferred (IE territory).

## Ingredients & scaling

- **Absolute quantities are FIRST-CLASS / canonical.** Every ingredient is
  `{name, qty, unit, role}` — what you actually weigh, what matches banneton / Dutch-oven
  capacity, and the only thing meaningful for non-bread or non-baking recipes (a custard
  has no "hydration").
- **Baker's % is an OPTIONAL derived lens.** A recipe *may* declare
  `scaling: { mode: bakers_percent, anchor: <ingredient> }`; then re-anchoring (change
  flour / target dough weight) recomputes quantities at fixed ratios. Recipes without it
  still scale by a plain **linear multiplier** ("1.5× batch"), or quantities just stand.
- **Caveat:** quantities scale linearly, but **bake time/temperature track loaf size/shape,
  not batch total** — flag bake-time for review when scaling changes loaf count/size.
- Composes with forking: children inherit their portion (600 g focaccia / 400 g pizza).

## Deviations: instance = editable overlay (not a frozen copy)

- At bake start the instance **snapshots the template** of a specific **recipe version**
  (`recipe_id` + `version`). Later recipe edits never rewrite past bakes; enables
  "compare my v3 vs v4 bakes."
- The instance is a **living overlay**: rescale · modify/add/omit an ingredient on a node ·
  **insert an ad-hoc node** ("added 50 g olives at shaping") · skip a node · record actual
  timings. **Every change is a tagged timeline event** (`type`, `node`, before→after,
  note, timestamp).
- **Template stays pristine; the instance is the source of truth for what actually
  happened.** The instance graph may **diverge structurally** from its template
  (added/skipped nodes) — that divergence *is* the record that powers lesson extraction
  and search ("show bakes where I upped hydration / added olives").

## Next

Build the **country loaf** end-to-end as the reference graph — levain back-schedule,
fold chain, preheat ∥ proof parallel branch with banneton/score prep, lid-on → lid-off
bake — to stress-test the schema on something real.
