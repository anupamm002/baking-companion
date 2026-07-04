import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baking_companion.engine import Engine          # noqa: E402
from baking_companion.recipe_loader import load_recipe  # noqa: E402
from baking_companion.store import Store             # noqa: E402

RECIPE_PATH = ROOT / "recipes" / "country_loaf.yaml"


@pytest.fixture
def recipe():
    return load_recipe(RECIPE_PATH)


@pytest.fixture
def store(tmp_path):
    return Store(home=tmp_path)


@pytest.fixture
def engine(store):
    return Engine(store)
