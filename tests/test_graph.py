import pytest

from baking_companion.graph import END, START, topo_order, validate_graph
from baking_companion.models import Recipe


def test_valid(recipe):
    assert validate_graph(recipe)
    order = topo_order(recipe)
    assert order[0] == START and order[-1] == END


def test_cycle_rejected():
    r = Recipe.from_dict({
        "id": "c", "name": "c", "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"from": "START", "to": "a"}, {"from": "a", "to": "b"},
                  {"from": "b", "to": "a"}, {"from": "b", "to": "END"}]})
    with pytest.raises(ValueError):
        validate_graph(r)


def test_unknown_node_rejected():
    r = Recipe.from_dict({
        "id": "c", "name": "c", "nodes": [{"id": "a"}],
        "edges": [{"from": "START", "to": "a"}, {"from": "a", "to": "ghost"}]})
    with pytest.raises(ValueError):
        validate_graph(r)
