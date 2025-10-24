"""Lightweight helper for interacting with a remote Ollama instance."""

from __future__ import annotations

import os
from typing import Dict, Iterable, Optional

import requests


class OllamaError(RuntimeError):
    """Raised when the Ollama backend returns an error."""


_DEFAULT_HOST = "69.142.141.135"
_DEFAULT_PORT = "11434"
_DEFAULT_MODEL = "gpt-oss:120b-cloud"


OLLAMA_HOST = os.getenv("OLLAMA_HOST", _DEFAULT_HOST)
OLLAMA_PORT = os.getenv("OLLAMA_PORT", _DEFAULT_PORT)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", f"http://{OLLAMA_HOST}:{OLLAMA_PORT}")


def _chat_endpoint() -> str:
    return f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"


def _tags_endpoint() -> str:
    return f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags"


def chat(
    messages: Iterable[Dict[str, str]],
    *,
    timeout: Optional[float] = 120,
    options: Optional[Dict[str, object]] = None,
) -> str:
    """Send a chat completion request to the configured Ollama backend."""

    payload: Dict[str, object] = {
        "model": OLLAMA_MODEL,
        "messages": list(messages),
        "stream": False,
    }

    if options:
        payload["options"] = options

    try:
        response = requests.post(_chat_endpoint(), json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise OllamaError("Failed to reach the Ollama server") from exc

    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover - unexpected payload
        raise OllamaError("Ollama returned a non-JSON response") from exc

    message = data.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    if "response" in data and isinstance(data["response"], str):
        return data["response"]

    raise OllamaError("Unexpected response format from Ollama")


def check_connection(timeout: float = 5.0) -> bool:
    """Return True when the configured model is reachable on the Ollama server."""

    try:
        response = requests.get(_tags_endpoint(), timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError):  # pragma: no cover - network failure
        return False

    models = body.get("models")
    if isinstance(models, list):
        for entry in models:
            if isinstance(entry, dict) and entry.get("name") == OLLAMA_MODEL:
                return True

    return False
