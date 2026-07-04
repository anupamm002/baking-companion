from baking_companion.scale import anchor_total, re_anchor, scale


def _bread_flour(r):
    node = next(n for n in r.nodes if n.id == "autolyse")
    return next(i for i in node.ingredients if i.name == "bread flour").qty


def test_anchor_total_positive(recipe):
    assert anchor_total(recipe) > 0


def test_scale_half(recipe):
    assert _bread_flour(scale(recipe, 0.5)) == 225


def test_re_anchor_identity(recipe):
    r = re_anchor(recipe, anchor_total(recipe))
    assert abs(_bread_flour(r) - 450) < 0.01


def test_re_anchor_double(recipe):
    r = re_anchor(recipe, 2 * anchor_total(recipe))
    assert abs(_bread_flour(r) - 900) < 0.01
