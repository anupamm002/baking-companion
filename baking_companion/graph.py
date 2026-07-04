"""DAG utilities over a Recipe, with implicit START and END sentinels."""
from __future__ import annotations

from collections import defaultdict, deque

START = "START"
END = "END"


def build_adjacency(recipe):
    succ = defaultdict(list)
    pred = defaultdict(list)
    for e in recipe.edges:
        succ[e.from_].append(e.to)
        pred[e.to].append(e.from_)
    return succ, pred


def _all_ids(recipe):
    return {n.id for n in recipe.nodes} | {START, END}


def validate_graph(recipe):
    ids = _all_ids(recipe)
    for e in recipe.edges:
        if e.from_ not in ids:
            raise ValueError(f"Edge references unknown node {e.from_!r}")
        if e.to not in ids:
            raise ValueError(f"Edge references unknown node {e.to!r}")
        if e.constraint and e.constraint.target not in ids:
            raise ValueError(f"Constraint target unknown: {e.constraint.target!r}")
    # acyclic via Kahn's algorithm
    succ, _ = build_adjacency(recipe)
    indeg = {n: 0 for n in ids}
    for n in ids:
        for m in succ.get(n, []):
            indeg[m] += 1
    q = deque([n for n in ids if indeg[n] == 0])
    seen = 0
    while q:
        n = q.popleft()
        seen += 1
        for m in succ.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if seen != len(ids):
        raise ValueError("Recipe graph has a cycle")
    return True


def topo_order(recipe):
    ids = _all_ids(recipe)
    succ, _ = build_adjacency(recipe)
    indeg = {n: 0 for n in ids}
    for n in ids:
        for m in succ.get(n, []):
            indeg[m] += 1
    q = deque([n for n in ids if indeg[n] == 0])
    order = []
    while q:
        n = q.popleft()
        order.append(n)
        for m in succ.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    return order


def predecessors(recipe, node_id):
    _, pred = build_adjacency(recipe)
    return pred.get(node_id, [])


def successors(recipe, node_id):
    succ, _ = build_adjacency(recipe)
    return succ.get(node_id, [])
