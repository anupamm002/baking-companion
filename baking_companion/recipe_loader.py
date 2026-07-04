"""Load and validate a recipe YAML into a Recipe model."""
from __future__ import annotations

from pathlib import Path

import yaml

from .graph import validate_graph
from .models import Recipe


def load_recipe(path):
    path = Path(path)
    data = yaml.safe_load(path.read_text())
    if isinstance(data, dict) and "recipe" in data:
        data = data["recipe"]
    recipe = Recipe.model_validate(data)
    validate_graph(recipe)
    return recipe
