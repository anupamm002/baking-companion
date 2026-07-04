"""The dialogue manager: the FSM/graph orchestrates, the LLM is one escalation tool.

Tier-0 intents are handled locally against the engine + scheduler. Judgment or
low-confidence turns escalate to Tier-1 with a locally-assembled context bundle
(current frontier + neighbours + recent notes + the question) — never transcript history.
"""
from __future__ import annotations

import difflib

from . import llm
from .duration import format_duration
from .intents import _norm, classify, content_words
from .scheduler import compute_schedule


def _clock(dt):
    return dt.strftime("%H:%M") if dt else "—"


class Router:
    def __init__(self, store, engine):
        self.store = store
        self.engine = engine

    def handle(self, utterance, bake_id):
        bake = self.store.get_bake(bake_id)
        recipe = self.engine.recipe_of(bake)
        states = self.store.get_node_states(bake_id)
        intent, conf = classify(utterance)
        if intent is None:
            return self._tier1(utterance, recipe, states, bake_id)
        handler = getattr(self, f"_do_{intent}", None)
        if handler is None:
            return self._tier1(utterance, recipe, states, bake_id)
        resp = handler(utterance, recipe, states, bake_id)
        resp.setdefault("tier", 0)
        resp["intent"] = intent
        resp["confidence"] = conf
        return resp

    # --- node resolution ---
    def _resolve_node(self, recipe, states, utterance):
        nmap = recipe.node_map()
        cw = content_words(utterance)
        order = [n.id for n in recipe.nodes]
        status = {s["node_id"]: s["status"] for s in states}
        # nodes sharing a content word with the utterance
        matches = []
        for n in recipe.nodes:
            label = set(_norm(n.id.replace("_", " ") + " " + (n.title or "")).split())
            if cw & label:
                matches.append(n.id)
        if matches:
            pending = [m for m in matches if status.get(m) not in ("done", "skipped")]
            pool = pending or matches
            if "next" in _norm(utterance).split():
                return min(pool, key=lambda m: order.index(m))
            # earliest matching node otherwise
            return min(pool, key=lambda m: order.index(m))
        # fall back to current/next frontier
        active = [s["node_id"] for s in states if s["status"] == "active"]
        ready = [s["node_id"] for s in states if s["status"] == "ready"]
        if "next" in _norm(utterance).split():
            return (ready or active or [None])[0]
        return (active or ready or [None])[0]

    def _frontier(self, states):
        return [s["node_id"] for s in states if s["status"] in ("ready", "active")]

    # --- Tier-0 handlers ---
    def _do_status(self, utterance, recipe, states, bake_id):
        nmap = recipe.node_map()
        parts = []
        for nid in self._frontier(states):
            parts.append(nmap[nid].title or nid)
        text = ("You're on: " + ", ".join(parts)) if parts else "Nothing active yet."
        return {"text": text, "frontier": self._frontier(states)}

    def _do_next(self, utterance, recipe, states, bake_id):
        nmap = recipe.node_map()
        ready = [s["node_id"] for s in states if s["status"] == "ready"]
        if not ready:
            active = [s["node_id"] for s in states if s["status"] == "active"]
            if active:
                n = nmap[active[0]]
                return {"text": f"Still in progress: {n.title}. {n.says or ''}".strip()}
            return {"text": "No next step — you may be done!"}
        n = nmap[ready[0]]
        return {"text": f"Next: {n.title}. {n.says or ''}".strip(), "node": n.id}

    def _do_time_left(self, utterance, recipe, states, bake_id):
        sched = compute_schedule(recipe, states)
        node = self._resolve_node(recipe, states, utterance)
        nmap = recipe.node_map()
        if node and node in sched["finish"]:
            fin = sched["finish"][node]
            remaining = fin - sched["now"]
            title = nmap[node].title or node
            return {"text": f"{title} should be done around {_clock(fin)} "
                            f"(~{format_duration(remaining)} from now).",
                    "node": node, "finish": _clock(fin)}
        return {"text": f"Projected finish is around {_clock(sched['finish'].get('END'))}."}

    def _do_show(self, utterance, recipe, states, bake_id):
        node = self._resolve_node(recipe, states, utterance)
        n = recipe.node_map().get(node)
        if not n:
            return {"text": "Which step did you mean?"}
        bits = [n.title or node]
        if n.ingredients:
            ings = ", ".join(
                f"{i.qty:g} {i.unit} {i.name}" if i.qty is not None else i.name
                for i in n.ingredients)
            bits.append("Ingredients: " + ings)
        if n.temperature:
            bits.append(f"Temperature {n.temperature}")
        if n.duration and n.duration.typical:
            bits.append(f"about {format_duration(n.duration.typical)}")
        if n.readiness_hint:
            bits.append(f"Ready when {n.readiness_hint}")
        return {"text": ". ".join(bits), "node": node}

    def _do_begin(self, utterance, recipe, states, bake_id):
        node = self._resolve_node(recipe, states, utterance)
        if not node:
            return {"text": "Which step should I start?"}
        self.engine.begin(bake_id, node)
        n = recipe.node_map()[node]
        return {"text": f"Started {n.title}. {n.says or ''}".strip(), "node": node,
                "action": "begin"}

    def _do_done(self, utterance, recipe, states, bake_id):
        node = self._resolve_node(recipe, states, utterance)
        if not node:
            return {"text": "Which step is done?"}
        self.engine.done(bake_id, node)
        new_states = self.store.get_node_states(bake_id)
        ready = [s["node_id"] for s in new_states if s["status"] == "ready"]
        nmap = recipe.node_map()
        nxt = f" Next up: {nmap[ready[0]].title}." if ready else ""
        return {"text": f"Marked {nmap[node].title} done.{nxt}", "node": node,
                "action": "done"}

    def _do_capture(self, utterance, recipe, states, bake_id):
        node = self._resolve_node(recipe, states, utterance)
        kind = "video" if ("video" in utterance or "record" in utterance) else "photo"
        return {"text": f"Ready to capture a {kind} for {node}.",
                "action": "capture", "node": node, "kind": kind}

    def _do_note(self, utterance, recipe, states, bake_id):
        # a note's free text shouldn't be fuzzy-matched — attach to the current step
        active = [s["node_id"] for s in states if s["status"] == "active"]
        ready = [s["node_id"] for s in states if s["status"] == "ready"]
        node = (active or ready or [None])[0]
        text = _strip_lead(utterance)
        self.engine.note(bake_id, node, text)
        where = f" ({node})" if node else ""
        return {"text": f"Noted{where}.", "node": node, "action": "note"}

    def _do_when(self, utterance, recipe, states, bake_id):
        sched = compute_schedule(recipe, states)
        lines = [f"Projected finish ~{_clock(sched['finish'].get('END'))}."]
        for s in sorted(sched["suggestions"], key=lambda x: x["when"]):
            lines.append(f"Start {s['node']} around {_clock(s['when'])}.")
        return {"text": " ".join(lines), "suggestions": sched["suggestions"]}

    # --- Tier-1 escalation ---
    def _context_bundle(self, utterance, recipe, states, bake_id):
        nmap = recipe.node_map()
        frontier = self._frontier(states)
        lines = [f"Recipe: {recipe.name} (v{recipe.version})."]
        lines.append("Current step(s):")
        for nid in frontier:
            n = nmap[nid]
            lines.append(f"  - {n.title}: {n.description or ''} "
                         f"Ready when: {n.readiness_hint or 'n/a'}.")
        recent = self.store.get_events(bake_id)[-6:]
        if recent:
            lines.append("Recent events:")
            for e in recent:
                lines.append(f"  - {e['type']} {e['node_id'] or ''}: {e['payload']}")
        lines.append(f"\nBaker's question: {utterance}")
        return "\n".join(lines)

    def _tier1(self, utterance, recipe, states, bake_id):
        bundle = self._context_bundle(utterance, recipe, states, bake_id)
        if not llm.available():
            return {"tier": 1, "intent": "escalate",
                    "text": "[Tier-1 reasoning needed — set OPENROUTER_API_KEY to enable. "
                            "Context that would be sent:]\n" + bundle,
                    "escalated": True, "bundle": bundle}
        system = [{"type": "text",
                   "text": "You are a concise, expert baking assistant. Use the provided "
                           "bake state to answer. Prefer dough-state cues over the clock. "
                           "1-3 sentences.",
                   "cache_control": {"type": "ephemeral"}}]
        answer = llm.chat([{"role": "system", "content": system},
                           {"role": "user", "content": bundle}])
        return {"tier": 1, "intent": "escalate", "text": answer,
                "escalated": True, "bundle": bundle}


def _strip_lead(utterance):
    u = utterance.strip()
    for lead in ("note that", "make a note that", "note", "remember that", "log that"):
        if u.lower().startswith(lead):
            return u[len(lead):].strip(" :,.") or u
    return u
