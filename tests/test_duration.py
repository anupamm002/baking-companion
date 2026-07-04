from datetime import timedelta

import pytest

from baking_companion.duration import format_duration, parse_duration


def test_parse():
    assert parse_duration("30m") == timedelta(minutes=30)
    assert parse_duration("1h30m") == timedelta(minutes=90)
    assert parse_duration("7h") == timedelta(hours=7)
    assert parse_duration(90) == timedelta(seconds=90)
    assert parse_duration(None) is None


def test_format():
    assert format_duration(timedelta(minutes=90)) == "1h30m"
    assert format_duration(timedelta(minutes=30)) == "30m"
    assert format_duration(None) == "—"


def test_bad_unit():
    with pytest.raises(ValueError):
        parse_duration("banana")
