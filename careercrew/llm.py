"""One small helper for calling the chat model outside the crew.

What it does: sends a prompt when OPENAI_API_KEY is set.
Who calls it: the interview, prep, and coaching modules.
What it returns: the model text, or an empty string when the call fails.

Some newer models (reasoning-style endpoints such as ``gpt-6-luna``) reject
``temperature`` outright with a 400 "unsupported value". Sending it makes every
prep-coach, mock-interview, and post-coach call fail. Rather than pinning the
helper to one model family, we send the tuning parameters the model accepts:
on the first rejection we drop them, retry once, and remember the model so the
next call skips them entirely.

Every request is time-bounded. These callbacks run inside the Gradio queue, so
a stalled HTTP call would leave the tab spinning on "processing" forever
instead of degrading to the deterministic fallback.
"""

from __future__ import annotations

import logging

from careercrew.config import get_settings

logger = logging.getLogger("careercrew.llm")

#: Seconds to wait for a single completion before giving up.
REQUEST_TIMEOUT = 90.0
#: One retry only: a retry storm inside the UI queue is worse than a fallback.
MAX_RETRIES = 1

#: Models seen rejecting ``temperature``; remembered so we stop re-sending it.
_NO_TEMPERATURE_MODELS: set[str] = set()


def available() -> bool:
    return get_settings().has_llm


def _client():
    from openai import OpenAI

    settings = get_settings()
    kwargs: dict = {
        "api_key": settings.openai_api_key,
        "timeout": REQUEST_TIMEOUT,
        "max_retries": MAX_RETRIES,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def _rejects_temperature(exc: Exception) -> bool:
    """True when the error says this model will not accept ``temperature``."""
    message = str(exc).lower()
    return "temperature" in message and ("unsupported" in message or "not support" in message)


def reset_model_capabilities() -> None:
    """Forget learned per-model capabilities (tests / model switches)."""
    _NO_TEMPERATURE_MODELS.clear()


def chat_completion(prompt: str, *, system: str = "", temperature: float = 0.3) -> str:
    """Return the model's text reply, or ``""`` on any failure."""
    if not available():
        return ""
    settings = get_settings()
    model = settings.openai_model
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict = {"model": model, "messages": messages}
    # Only send tuning knobs the model is known to accept.
    if model not in _NO_TEMPERATURE_MODELS:
        payload["temperature"] = temperature

    try:
        client = _client()
        try:
            response = client.chat.completions.create(**payload)
        except Exception as exc:  # noqa: BLE001 - inspect, maybe retry
            if "temperature" not in payload or not _rejects_temperature(exc):
                raise
            logger.info("model %s rejects temperature; retrying with defaults", model)
            _NO_TEMPERATURE_MODELS.add(model)
            payload.pop("temperature", None)
            response = client.chat.completions.create(**payload)
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 - callers fall back to deterministic paths
        logger.warning("chat completion failed: %s", exc)
        return ""


def callable_or_none():
    """Return :func:`chat_completion` when a key is set, else ``None``."""
    return chat_completion if available() else None
