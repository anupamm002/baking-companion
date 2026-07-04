from pathlib import Path

import pytest

from baking_companion.importer import extract_yaml, parse_and_validate  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def test_valid_yaml_roundtrips():
    raw = "```yaml\n" + (ROOT / "recipes/country_loaf.yaml").read_text() + "\n```"
    r = parse_and_validate(extract_yaml(raw))
    assert r.id == "country_loaf"
    assert len(r.nodes) == 16


def test_extract_yaml_strips_fences():
    inner = "recipe:\n  id: x\n  name: X"
    # closed fence
    assert extract_yaml(f"```yaml\n{inner}\n```") == inner
    # unclosed fence (the real bug: reply started with ```yaml and no closer)
    assert extract_yaml(f"```yaml\n{inner}") == inner
    # plain ``` with no language tag
    assert extract_yaml(f"```\n{inner}\n```") == inner
    # no fence at all
    assert extract_yaml(inner) == inner


def test_importer_rejects_cyclic_output():
    bad = (
        "recipe:\n  id: b\n  name: b\n  nodes: [{id: a}, {id: c}]\n  edges:\n"
        "    - {from: START, to: a}\n    - {from: a, to: c}\n"
        "    - {from: c, to: a}\n    - {from: c, to: END}\n")
    with pytest.raises(Exception):
        parse_and_validate(bad)
