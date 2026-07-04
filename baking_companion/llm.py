"""Minimal OpenRouter client (stdlib urllib — no extra dependencies).

Tier-1 reasoning goes through the user's OpenRouter key. Static/system content is sent
with Anthropic-style `cache_control` so repeated calls hit the prompt cache.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("BAKING_LLM_MODEL", "anthropic/claude-sonnet-4.6")


class LLMError(RuntimeError):
    pass


def available():
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def chat(messages, model=None, temperature=0.2, max_tokens=4000):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY not set")
    body = json.dumps({
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        OPENROUTER_URL, data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/baking-companion",
            "X-Title": "Baking Companion",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise LLMError(f"OpenRouter HTTP {e.code}: {e.read().decode(errors='ignore')}")
    except urllib.error.URLError as e:
        raise LLMError(f"OpenRouter request failed: {e}")
    return data["choices"][0]["message"]["content"]
