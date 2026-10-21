"""One small helper for calling the chat model outside the crew.

What it does: sends a prompt when OPENAI_API_KEY is set.
Who calls it: the interview, prep, and coaching modules.
What it returns: the model text, or an empty string when the call fails.
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
