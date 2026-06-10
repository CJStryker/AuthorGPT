"""Lightweight helper for interacting with an Ollama instance."""

from __future__ import annotations

import os
from typing import Dict, Iterable, Optional

import requests


class OllamaError(RuntimeError):
    """Raised when the Ollama backend returns an error."""


_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = "11434"
_DEFAULT_MODEL = "llama3.1"
_DEFAULT_TIMEOUT = 300.0


OLLAMA_HOST = os.getenv("OLLAMA_HOST", _DEFAULT_HOST)
OLLAMA_PORT = os.getenv("OLLAMA_PORT", _DEFAULT_PORT)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", f"http://{OLLAMA_HOST}:{OLLAMA_PORT}")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", str(_DEFAULT_TIMEOUT)))


def normalize_base_url(base_url: Optional[str] = None) -> str:
    """Return a clean Ollama base URL without a trailing slash."""

    return (base_url or OLLAMA_BASE_URL).strip().rstrip("/")


def _chat_endpoint(base_url: Optional[str] = None) -> str:
    return f"{normalize_base_url(base_url)}/api/chat"


def _tags_endpoint(base_url: Optional[str] = None) -> str:
    return f"{normalize_base_url(base_url)}/api/tags"


def chat(
    messages: Iterable[Dict[str, str]],
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    options: Optional[Dict[str, object]] = None,
) -> str:
    """Send a chat completion request to the configured Ollama backend."""

    payload: Dict[str, object] = {
        "model": model or OLLAMA_MODEL,
        "messages": list(messages),
        "stream": False,
    }

    if options:
        payload["options"] = options

    request_timeout = OLLAMA_TIMEOUT if timeout is None else timeout

    try:
        response = requests.post(_chat_endpoint(base_url), json=payload, timeout=request_timeout)
    except requests.Timeout as exc:  # pragma: no cover - network failure
        raise OllamaError(
            f"Timed out waiting for Ollama after {request_timeout} seconds. "
            "Try a smaller book, a faster model, or increase OLLAMA_TIMEOUT."
        ) from exc
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise OllamaError(f"Failed to reach the Ollama server at {normalize_base_url(base_url)}") from exc

    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover - unexpected payload
        raise OllamaError(f"Ollama returned a non-JSON response with status {response.status_code}") from exc

    if not response.ok:
        detail = data.get("error") if isinstance(data, dict) else None
        raise OllamaError(f"Ollama returned HTTP {response.status_code}: {detail or response.text[:200]}")

    if not isinstance(data, dict):
        raise OllamaError("Unexpected response format from Ollama")

    if data.get("error"):
        raise OllamaError(str(data["error"]))

    message = data.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    if "response" in data and isinstance(data["response"], str) and data["response"].strip():
        return data["response"].strip()

    raise OllamaError("Ollama returned an empty response")


def list_models(*, base_url: Optional[str] = None, timeout: float = 5.0) -> list[str]:
    """Return model names advertised by an Ollama server."""

    try:
        response = requests.get(_tags_endpoint(base_url), timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:  # pragma: no cover - network failure
        raise OllamaError(f"Unable to connect to the Ollama server at {normalize_base_url(base_url)}") from exc

    models = body.get("models")
    if not isinstance(models, list):
        raise OllamaError("Unexpected model list format from Ollama")

    names: list[str] = []
    for entry in models:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            names.append(entry["name"])

    return names


def check_connection(
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 5.0,
    require_model: bool = True,
) -> bool:
    """Return True when the Ollama server is reachable and, optionally, has the model."""

    try:
        names = list_models(base_url=base_url, timeout=timeout)
    except OllamaError:
        return False

    selected_model = model or OLLAMA_MODEL
    return selected_model in names if require_model else True
