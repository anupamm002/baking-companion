from baking_companion.models import Recipe


def _divide_recipe():
    return Recipe.from_dict({
        "id": "div", "name": "Divide",
        "nodes": [{"id": "mix"}, {"id": "divide"},
                  {"id": "loaf_bake"}, {"id": "foc_bake"}],
        "edges": [{"from": "START", "to": "mix"}, {"from": "mix", "to": "divide"},
                  {"from": "divide", "to": "loaf_bake"},
                  {"from": "divide", "to": "foc_bake"},
                  {"from": "loaf_bake", "to": "END"},
                  {"from": "foc_bake", "to": "END"}]})


def test_fork_seeds_child_and_records_lineage(engine, store):
    r = _divide_recipe()
    parent = engine.create_bake(r, name="parent")
    child = engine.fork(parent, r, satisfied_nodes=["mix", "divide"], name="pizza")

    st = {s["node_id"]: s["status"] for s in store.get_node_states(child)}
    assert st["mix"] == "done" and st["divide"] == "done"
    assert st["loaf_bake"] == "ready" and st["foc_bake"] == "ready"

    child_events = {e["type"] for e in store.get_events(child)}
    parent_events = {e["type"] for e in store.get_events(parent)}
    assert "forked_from" in child_events
    assert "fork" in parent_events
