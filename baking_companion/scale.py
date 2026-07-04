"""Ingredient scaling. Absolute quantities are canonical; this re-anchors them.

- bakers_percent: sum the anchor role/ingredient (e.g. total flour), scale everything by
  new_total / old_total so ratios (hydration, salt %, leaven %) are preserved.
- linear: multiply all quantities by a factor.
"""
from __future__ import annotations

import re


def _norm(s):
    return re.sub(r"[^a-z0-9]", " ", (s or "").lower()).strip()


def _matches_anchor(ing, anchor):
    a = _norm(anchor)
    if ing.role and _norm(ing.role) == a:
        return True
    name = _norm(ing.name)
    return a == name or a in name.split()


def anchor_total(recipe):
    if not recipe.scaling or not recipe.scaling.anchor:
        raise ValueError("recipe has no scaling anchor")
    total = 0.0
    for n in recipe.nodes:
        for ing in n.ingredients:
            if ing.qty is not None and _matches_anchor(ing, recipe.scaling.anchor):
                total += ing.qty
    return total


def scale(recipe, factor):
    """Return a deep copy with every ingredient quantity multiplied by factor."""
    r = recipe.copy_deep()
    for n in r.nodes:
        for ing in n.ingredients:
            if ing.qty is not None:
                ing.qty = round(ing.qty * factor, 2)
    return r


def re_anchor(recipe, new_anchor_total):
    """Scale so the anchor role/ingredient totals `new_anchor_total`."""
    old = anchor_total(recipe)
    if not old:
        raise ValueError("anchor total is zero; cannot re-anchor")
    return scale(recipe, new_anchor_total / old)
