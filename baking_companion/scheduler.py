"""First-pass scheduler over the DAG.

Forward pass: project start/finish for every node using actual timestamps where known
and typical (or overridden) durations elsewhere. Backward: turn edge constraints into
"start X now" suggestions (preheat, pull-and-score, levain feed).

Re-run from scratch on every call — timing drift just re-flows.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .graph import END, START, build_adjacency, topo_order


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def expected_duration(node, state):
    if state and state.get("expected_seconds"):
        return timedelta(seconds=state["expected_seconds"])
    if node is not None and node.duration:
        for cand in (node.duration.typical, node.duration.min, node.duration.max):
            if cand:
                return cand
    return timedelta(0)


def compute_schedule(recipe, states, now=None):
    now = now or datetime.now().astimezone()
    nmap = recipe.node_map()
    smap = {s["node_id"]: dict(s) for s in states}
    _, pred = build_adjacency(recipe)

    start, finish = {}, {}
    for nid in topo_order(recipe):
        if nid == START:
            finish[nid] = now
            continue
        preds = pred.get(nid, [])
        pred_finish = max([finish.get(p, now) for p in preds], default=now)
        if nid == END:
            start[nid] = pred_finish
            finish[nid] = pred_finish
            continue
        node = nmap.get(nid)
        st = smap.get(nid, {})
        status = st.get("status")
        dur = expected_duration(node, st)
        if status == "done":
            s = _parse_dt(st.get("started_at")) or pred_finish
            f = _parse_dt(st.get("completed_at")) or (s + dur)
        elif status == "active":
            s = _parse_dt(st.get("started_at")) or now
            f = max(now, s + dur)
        else:
            s = max(pred_finish, now)
            f = s + dur
        start[nid], finish[nid] = s, f

    suggestions = []
    for e in recipe.edges:
        c = e.constraint
        if not c or e.from_ in (START, END):
            continue
        tgt_start = start.get(c.target)
        if tgt_start is None:
            continue
        node = nmap.get(e.from_)
        if c.kind == "finish_by":
            when = tgt_start - expected_duration(node, smap.get(e.from_, {}))
        elif c.kind == "start_before":
            when = tgt_start - (c.lead or timedelta(0))
        else:  # no_earlier_than
            when = tgt_start
        suggestions.append({"node": e.from_, "kind": c.kind,
                            "target": c.target, "when": when})

    return {"start": start, "finish": finish, "suggestions": suggestions, "now": now}
