"""Tier-0 intent classification: rules + fuzzy matching (stdlib difflib, no ML).

Small, domain-specific vocabulary → a rules baseline is debuggable and doubles as the
eval set. Low confidence or a judgment cue routes to Tier-1 (the LLM).
"""
from __future__ import annotations

import difflib
import re

INTENT_PHRASES = {
    "status": ["status", "where am i", "what's happening", "current state",
               "hows it going", "what's going on"],
    "next": ["what's next", "next step", "what do i do now", "what now",
             "what should i do"],
    "time_left": ["how long", "time left", "how much time", "when will", "when is",
                  "eta", "ready at", "how long until", "time until", "when do i"],
    "show": ["show", "details", "ingredients", "how much", "what temperature",
             "recipe for", "tell me about", "what goes in", "how many grams"],
    "begin": ["begin", "start the", "im starting", "starting the", "kick off"],
    "done": ["done", "finished", "complete", "completed", "mark it done",
             "thats done", "fold done"],
    "capture": ["take a photo", "take a picture", "capture", "photo", "picture",
                "take a video", "record this", "snap"],
    "note": ["note", "remember that", "log that", "make a note", "jot down"],
    "when": ["schedule", "when should i preheat", "prep alerts", "the plan",
             "when to start", "timeline", "whats the plan"],
}

# Judgment cues force Tier-1 even if a Tier-0 keyword also matches.
TIER1_CUES = ["why", "does this look", "is it ready", "is this ready",
              "looks like", "too dense", "risen enough", "how does",
              "what do you think", "over proof", "under proof", "overproofed",
              "underproofed", "compare", "does it look", "look right", "look ok"]

_STOP = {"the", "a", "an", "how", "long", "until", "is", "it", "ready", "when",
         "will", "next", "my", "for", "to", "of", "and", "i", "do", "should",
         "me", "on", "in", "s", "whats", "what", "much", "many", "now", "this",
         "that", "give", "show", "tell", "about", "time", "left", "step"}


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def _padded(s):
    return f" {s} "


def classify(utterance):
    """Return (intent_name, confidence). intent None means 'escalate to Tier-1'."""
    u = _norm(utterance)
    pu = _padded(u)
    for cue in TIER1_CUES:
        if _padded(cue) in pu or cue in u and " " in cue:
            return None, 0.0
    best, score = None, 0.0
    for name, phrases in INTENT_PHRASES.items():
        s = _phrase_score(u, phrases)
        if s > score:
            best, score = name, s
    if score < 0.45:
        return None, score
    return best, round(score, 2)


def _phrase_score(u, phrases):
    words = set(u.split())
    best = 0.0
    for p in phrases:
        pw = set(p.split())
        if p in u:
            best = max(best, 0.9)
        overlap = len(pw & words) / max(len(pw), 1)
        best = max(best, overlap)
        best = max(best, difflib.SequenceMatcher(None, u, p).ratio() * 0.8)
    return min(best, 1.0)


def content_words(utterance):
    return {w for w in _norm(utterance).split() if w not in _STOP and len(w) > 1}
