"""Recipe library: user recipes stored as YAML under <home>/recipes/.

Kept separate from the repo's bundled recipes/ so user edits are writable and persistent.
Seeded from the bundled recipes on first run.
"""
from __future__ import annotations

from pathlib import Path

from .importer import parse_and_validate
from .recipe_loader import load_recipe


def lib_dir(home):
    d = Path(home) / "recipes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def seed(home, bundled_dir):
    d = lib_dir(home)
    if any(d.glob("*.yaml")):
        return
    bundled = Path(bundled_dir)
    if bundled.exists():
        for f in bundled.glob("*.yaml"):
            (d / f.name).write_text(f.read_text())


def list_recipes(home):
    out = []
    for f in sorted(lib_dir(home).glob("*.yaml")):
        try:
            r = load_recipe(f)
            out.append({"id": r.id, "name": r.name, "version": r.version,
                        "nodes": len(r.nodes), "file": f.name})
        except Exception as e:                       # keep broken files visible
            out.append({"id": f.stem, "name": f.stem, "error": str(e), "file": f.name})
    return out


def get_yaml(home, rid):
    f = lib_dir(home) / f"{rid}.yaml"
    return f.read_text() if f.exists() else None


def save_yaml(home, yaml_text):
    recipe = parse_and_validate(yaml_text)           # validates schema + DAG; raises
    (lib_dir(home) / f"{recipe.id}.yaml").write_text(yaml_text.strip() + "\n")
    return recipe


def delete(home, rid):
    f = lib_dir(home) / f"{rid}.yaml"
    if f.exists():
        f.unlink()
        return True
    return False
