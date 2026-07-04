"""Parse and format human durations like '30m', '7h', '1h30m'."""
from __future__ import annotations

import re
from datetime import timedelta

_TOKEN = re.compile(r"(?P<val>\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z]+)")
_UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
}


def parse_duration(value):
    """Accept a timedelta, seconds (int/float), or a string like '1h30m'."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))
    s = str(value).strip().lower()
    if not s:
        return None
    total = 0.0
    matched = False
    for m in _TOKEN.finditer(s):
        unit = m.group("unit")
        if unit not in _UNIT_SECONDS:
            raise ValueError(f"Unknown duration unit {unit!r} in {value!r}")
        total += float(m.group("val")) * _UNIT_SECONDS[unit]
        matched = True
    if not matched:
        raise ValueError(f"Cannot parse duration {value!r}")
    return timedelta(seconds=total)


def format_duration(td):
    """Render a timedelta compactly, e.g. '1h30m'."""
    if td is None:
        return "—"
    secs = int(td.total_seconds())
    sign = "-" if secs < 0 else ""
    secs = abs(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if not parts:
        parts.append(f"{s}s" if s else "0m")
    return sign + "".join(parts)
