"""CareerCrew - a tiny LLM helper.

The interview, prep, and coaching modules take an optional ``llm`` callable so
they stay testable and dependency-free. This module provides the real callable
backed by the OpenAI chat API, used by the UI when an API key is configured.

``available()`` reports whether a key exists; ``chat_completion`` never raises
(it returns ``""`` on failure) so callers fall back to their deterministic path.
"""

from __future__ import annotations

import logging

from careercrew.config import get_settings

logger = logging.getLogger("careercrew.llm")


def available() -> bool:
    return get_settings().has_llm


def _client():
    from openai import OpenAI

    settings = get_settings()
    kwargs: dict = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def chat_completion(prompt: str, *, system: str = "", temperature: float = 0.3) -> str:
    """Return the model's text reply, or ``""`` on any failure."""
    if not available():
        return ""
    settings = get_settings()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        response = _client().chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 - callers fall back to deterministic paths
        logger.warning("chat completion failed: %s", exc)
        return ""


def callable_or_none():
    """Return :func:`chat_completion` when a key is set, else ``None``."""
    return chat_completion if available() else None
