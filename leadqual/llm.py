"""Tiny LLM client over plain HTTP (no SDK needed). Claude first, OpenAI second."""
from __future__ import annotations

import json
import os
import re

import requests


def provider() -> str:
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "rules"


def complete_json(system: str, user: str, session: requests.Session | None = None) -> dict:
    """Ask the model for a single JSON object and parse it."""
    s = session or requests
    p = provider()
    if p == "anthropic":
        r = s.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"), "max_tokens": 800, "system": system,
                  "messages": [{"role": "user", "content": user}]},
            timeout=60,
        )
        r.raise_for_status()
        text = "".join(b["text"] for b in r.json()["content"] if b["type"] == "text")
    elif p == "openai":
        r = s.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "temperature": 0, "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=60,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    else:
        raise RuntimeError("No LLM key configured")
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"Model did not return JSON: {text[:200]}")
    return json.loads(match.group(0))
