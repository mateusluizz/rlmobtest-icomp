"""Ollama server and model availability utilities."""

import json
import urllib.error
import urllib.request

from rlmobtest.constants.llm import DEFAULT_LLM_MODEL, DEFAULT_OLLAMA_BASE_URL


def check_ollama_server(base_url: str = DEFAULT_OLLAMA_BASE_URL) -> bool:
    """Return True if the Ollama HTTP server is reachable.

    Only verifies connectivity — does NOT check model availability.
    Use check_ollama_model() when you need to confirm the model is installed.
    """
    try:
        with urllib.request.urlopen(base_url, timeout=3):
            return True
    except Exception:
        return False


def check_ollama_model(
    model: str = DEFAULT_LLM_MODEL,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
) -> bool:
    """Return True if the Ollama server is running AND the model is installed.

    Queries /api/tags and checks for an exact model name match.
    """
    try:
        tags_url = base_url.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(tags_url, timeout=3) as resp:
            data = json.loads(resp.read())
            installed = {m["name"] for m in data.get("models", [])}
            return model in installed
    except Exception:
        return False
