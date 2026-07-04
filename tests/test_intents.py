import pytest

from baking_companion.intents import classify


@pytest.mark.parametrize("text,intent", [
    ("where am I", "status"),
    ("what's next", "next"),
    ("how long until the levain is ready", "time_left"),
    ("how much water in the autolyse", "show"),
    ("when should I preheat", "when"),
    ("take a photo", "capture"),
])
def test_tier0_intents(text, intent):
    got, conf = classify(text)
    assert got == intent, f"{text!r} -> {got} (conf {conf})"


@pytest.mark.parametrize("text", [
    "why is my crumb so dense",
    "does this look ready to fold",
    "is it overproofed",
])
def test_judgment_escalates(text):
    got, _ = classify(text)
    assert got is None
