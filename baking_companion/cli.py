"""Command-line brain for the baking companion (Phase 1).

    bc start <recipe>         create a bake instance (recipe = ./recipes/<id>.yaml or a path)
    bc list                   list bakes
    bc use <bake_id>          set the current bake
    bc status                 marking + frontier + hints
    bc show <node>            full recipe detail for a node (no more printed recipe)
    bc begin <node> [--at T] [--expect 4h30m]
    bc done <node> [--at T]
    bc skip <node> [--reason ...]
    bc capture <node> <file> [--tags a,b] [--caption ...]
    bc note <node> <text...>
    bc when                   schedule: levain ready, next steps, ETA, prep alerts
    bc timeline               event log
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .duration import format_duration, parse_duration
from .engine import Engine
from .importer import import_recipe
from .recipe_loader import load_recipe
from .router import Router
from .scheduler import compute_schedule
from .store import Store, now_iso

RECIPES_DIR = Path(__file__).resolve().parent.parent / "recipes"

_STATUS_ICON = {"blocked": "·", "ready": "○", "active": "◉",
                "done": "✓", "skipped": "⤫"}


def _clock(dt):
    if not dt:
        return "—"
    today = datetime.now().astimezone().date()
    if dt.date() == today:
        return dt.strftime("%H:%M")
    return dt.strftime("%a %H:%M")   # e.g. "Sun 05:58" for next-day times


def _resolve_recipe(arg):
    p = Path(arg)
    if p.exists():
        return p
    cand = RECIPES_DIR / (arg if arg.endswith(".yaml") else f"{arg}.yaml")
    if cand.exists():
        return cand
    raise SystemExit(f"Recipe not found: {arg} (looked in {RECIPES_DIR})")


class App:
    def __init__(self):
        self.store = Store()
        self.engine = Engine(self.store)
        self._current = self.store.home / "current_bake.txt"

    # --- current-bake pointer ---
    def current(self):
        if self._current.exists():
            bid = self._current.read_text().strip()
            if self.store.get_bake(bid):
                return bid
        raise SystemExit("No current bake. Run `bc start <recipe>` or `bc use <id>`.")

    def set_current(self, bake_id):
        self._current.write_text(bake_id)

    # --- commands ---
    def cmd_start(self, a):
        recipe = load_recipe(_resolve_recipe(a.recipe))
        bake_id = self.engine.create_bake(recipe, name=a.name)
        self.set_current(bake_id)
        print(f"Started bake {bake_id}  ({recipe.name} v{recipe.version})")
        print("Set as current bake. `bc status` to see the frontier.")

    def cmd_list(self, a):
        for b in self.store.list_bakes():
            print(f"{b['id']:<34} {b['status']:<8} {b['name']}")

    def cmd_use(self, a):
        if not self.store.get_bake(a.bake_id):
            raise SystemExit(f"No such bake: {a.bake_id}")
        self.set_current(a.bake_id)
        print(f"Current bake set to {a.bake_id}")

    def cmd_status(self, a):
        bake_id = self.current()
        bake = self.store.get_bake(bake_id)
        recipe = self.engine.recipe_of(bake)
        state_list = self.store.get_node_states(bake_id)
        states = {s["node_id"]: s for s in state_list}
        sched = compute_schedule(recipe, state_list)
        deferred = {s["node"]: s["when"] for s in sched["suggestions"]}
        print(f"{bake['name']}  [{bake_id}]  status={bake['status']}\n")
        for n in recipe.nodes:
            st = states.get(n.id, {})
            status = st["status"] if st else "blocked"
            icon = _STATUS_ICON.get(status, "?")
            extra = ""
            if status == "active" and st["started_at"]:
                started = datetime.fromisoformat(st["started_at"])
                extra = f"  (started {_clock(started)}, {format_duration(datetime.now().astimezone() - started)} ago)"
            elif status == "ready" and n.id in deferred:
                extra = f"  (scheduled ~{_clock(deferred[n.id])})"
            print(f"  {icon} {n.id:<16} {status:<8} {n.title or ''}{extra}")
        frontier = [nid for nid, s in states.items() if s["status"] in ("ready", "active")]
        print("\nFrontier (actionable now): " + (", ".join(frontier) or "—"))

    def cmd_show(self, a):
        bake = self.store.get_bake(self.current())
        recipe = self.engine.recipe_of(bake)
        n = recipe.node_map().get(a.node)
        if not n:
            raise SystemExit(f"No node {a.node!r} in {recipe.id}")
        print(f"# {n.title or n.id}  [{n.id}] ({n.type})")
        if n.description:
            print(n.description)
        if n.ingredients:
            print("\nIngredients:")
            for ing in n.ingredients:
                qty = f"{ing.qty:g} {ing.unit}" if ing.qty is not None else ""
                print(f"  - {ing.name:<20} {qty}")
        if n.temperature:
            print(f"\nTemperature: {n.temperature}")
        if n.duration:
            d = n.duration
            print(f"Duration: typ {format_duration(d.typical)} "
                  f"(min {format_duration(d.min)}, max {format_duration(d.max)})")
        if n.readiness_hint:
            print(f"Ready when: {n.readiness_hint}")
        if n.references:
            print("\nReferences:")
            for r in n.references:
                loc = r.url or r.path or ""
                ts = f" @{r.t_start}" if r.t_start else ""
                print(f"  - [{r.type}] {loc}{ts}  {r.caption or ''}")
        past = self.store.get_media(recipe_id=recipe.id, node_id=n.id)
        if past:
            print(f"\nPast media for this step ({len(past)} across bakes):")
            for m in past[-5:]:
                print(f"  - {m['ts']}  {m['path']}")

    def cmd_begin(self, a):
        expected = parse_duration(a.expect) if a.expect else None
        self.engine.begin(self.current(), a.node, at=a.at, expected=expected)
        print(f"Began {a.node}" + (f" (expect {format_duration(expected)})" if expected else ""))

    def cmd_done(self, a):
        self.engine.done(self.current(), a.node, at=a.at)
        print(f"Marked {a.node} done. Newly ready steps updated.")

    def cmd_skip(self, a):
        self.engine.skip(self.current(), a.node, reason=a.reason)
        print(f"Skipped {a.node}.")

    def cmd_capture(self, a):
        tags = [t.strip() for t in a.tags.split(",")] if a.tags else []
        dest = self.engine.capture(self.current(), a.node, a.file,
                                   tags=tags, caption=a.caption)
        print(f"Captured → {dest}")

    def cmd_note(self, a):
        self.engine.note(self.current(), a.node, " ".join(a.text))
        print("Noted.")

    def cmd_when(self, a):
        bake_id = self.current()
        bake = self.store.get_bake(bake_id)
        recipe = self.engine.recipe_of(bake)
        states = self.store.get_node_states(bake_id)
        smap = {s["node_id"]: s for s in states}
        sched = compute_schedule(recipe, states)
        print(f"Now: {_clock(sched['now'])}\n")
        frontier = [s["node_id"] for s in states if s["status"] in ("ready", "active")]
        print("Next / in progress:")
        for nid in frontier:
            node = recipe.node_map().get(nid)
            print(f"  {nid:<16} done ~{_clock(sched['finish'].get(nid))}"
                  f"   {node.readiness_hint or ''}")
        print(f"\nProjected finish (END): ~{_clock(sched['finish'].get('END'))}")
        if sched["suggestions"]:
            print("\nPrep alerts (start these around):")
            for s in sorted(sched["suggestions"], key=lambda x: x["when"]):
                print(f"  {s['node']:<16} ~{_clock(s['when'])}   ({s['kind']} → {s['target']})")

    def cmd_timeline(self, a):
        for e in self.store.get_events(self.current()):
            print(f"  {e['ts']}  {e['type']:<10} {e['node_id'] or '':<16} {e['payload']}")

    def cmd_ping(self, a):
        from . import llm
        if not llm.available():
            print("OPENROUTER_API_KEY not set — Tier-1 disabled. See README.")
            return
        model = a.model or llm.DEFAULT_MODEL
        try:
            out = llm.chat([{"role": "user", "content": "Reply with exactly: OK"}],
                           model=model, max_tokens=10)
            print(f"✓ {model} responded: {out.strip()[:80]}")
        except Exception as e:
            print(f"✗ LLM error with {model}: {e}")

    def cmd_serve(self, a):
        from .web import serve
        bake = a.bake or (self._current.read_text().strip()
                          if self._current.exists() else None)
        serve(bake_id=bake, host=a.host, port=a.port, store=self.store)

    def cmd_ask(self, a):
        text = " ".join(a.text)
        router = Router(self.store, self.engine)
        resp = router.handle(text, self.current())
        tag = f"T{resp['tier']}·{resp.get('intent')}"
        if resp.get("confidence") is not None:
            tag += f"·{resp['confidence']}"
        print(f"[{tag}] {resp['text']}")

    def cmd_import(self, a):
        res = import_recipe(a.source, out_dir=a.out, model=a.model, dry_run=a.dry_run)
        if a.dry_run:
            print(f"# DRY RUN — prompt for source: {res['source_desc']}\n")
            for msg in res["messages"]:
                blocks = msg["content"]
                text = blocks if isinstance(blocks, str) else "\n".join(
                    b.get("text", f"[{b.get('type')}]") for b in blocks)
                print(f"--- {msg['role']} ---\n{text}\n")
            return
        if res["questions"]:
            print("Clarifying questions from the importer:")
            for q in res["questions"]:
                print("  " + q.lstrip("# "))
        print(f"Saved validated recipe → {res['path']}  "
              f"({res['recipe'].name} v{res['recipe'].version}, "
              f"{len(res['recipe'].nodes)} nodes)")


def build_parser():
    p = argparse.ArgumentParser(prog="bake", description="Baking companion")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start"); s.add_argument("recipe"); s.add_argument("--name")
    sub.add_parser("list")
    s = sub.add_parser("use"); s.add_argument("bake_id")
    sub.add_parser("status")
    s = sub.add_parser("show"); s.add_argument("node")
    s = sub.add_parser("begin"); s.add_argument("node")
    s.add_argument("--at"); s.add_argument("--expect")
    s = sub.add_parser("done"); s.add_argument("node"); s.add_argument("--at")
    s = sub.add_parser("skip"); s.add_argument("node"); s.add_argument("--reason")
    s = sub.add_parser("capture"); s.add_argument("node"); s.add_argument("file")
    s.add_argument("--tags"); s.add_argument("--caption")
    s = sub.add_parser("note"); s.add_argument("node"); s.add_argument("text", nargs="+")
    sub.add_parser("when")
    sub.add_parser("timeline")
    s = sub.add_parser("ask"); s.add_argument("text", nargs="+")
    s = sub.add_parser("ping"); s.add_argument("--model")
    s = sub.add_parser("serve"); s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8765); s.add_argument("--bake")
    s = sub.add_parser("import"); s.add_argument("source")
    s.add_argument("--out", default="recipes"); s.add_argument("--model")
    s.add_argument("--dry-run", action="store_true")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    app = App()
    getattr(app, f"cmd_{args.cmd}")(args)


if __name__ == "__main__":
    main()
