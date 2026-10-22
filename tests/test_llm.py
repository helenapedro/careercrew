"""Tests for the chat-completion helper used by the coach and interview tabs.

Regression cover for the "processing forever" bug: the app defaulted to a model
that rejects ``temperature``, so every prep-coach, mock-interview, and
post-coach call 400'd and silently degraded to the offline fallback.
"""

from __future__ import annotations

import pytest

from careercrew import llm


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]


class _FakeCompletions:
    """Records the kwargs of each call and can reject ``temperature``."""

    def __init__(self, *, rejects_temperature: bool = False, content: str = "ok") -> None:
        self.rejects_temperature = rejects_temperature
        self.content = content
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.rejects_temperature and "temperature" in kwargs:
            raise ValueError("temperature is not supported by this model")
        return _FakeResponse(self.content)


class _FakeClient:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.chat = type("Chat", (), {"completions": completions})()


@pytest.fixture(autouse=True)
def _clear_learned_capabilities():
    llm.reset_model_capabilities()
    yield
    llm.reset_model_capabilities()


@pytest.fixture
def fake_client(monkeypatch):
    """Point the helper at a fake client and pretend a key is configured."""

    def install(completions: _FakeCompletions) -> _FakeCompletions:
        monkeypatch.setattr(llm, "_client", lambda: _FakeClient(completions))
        monkeypatch.setattr(llm, "available", lambda: True)
        return completions

    return install


def test_sends_temperature_when_model_accepts_it(fake_client):
    completions = fake_client(_FakeCompletions(content="hello"))

    assert llm.chat_completion("hi") == "hello"
    assert completions.calls[0]["temperature"] == 0.3


def test_retries_without_temperature_when_model_rejects_it(fake_client):
    completions = fake_client(_FakeCompletions(rejects_temperature=True, content="recovered"))

    # The rejection must not surface as an empty string / fallback.
    assert llm.chat_completion("hi") == "recovered"
    assert len(completions.calls) == 2
    assert "temperature" in completions.calls[0]
    assert "temperature" not in completions.calls[1]


def test_remembers_the_model_so_later_calls_skip_temperature(fake_client):
    completions = fake_client(_FakeCompletions(rejects_temperature=True, content="ok"))

    llm.chat_completion("first")
    llm.chat_completion("second")

    # First call: rejected attempt + retry = 2. Second call skips the doomed
    # attempt, so 1 more. Without the learned capability this would be 4.
    assert len(completions.calls) == 3
    assert "temperature" not in completions.calls[-1]


def test_other_errors_are_not_retried(fake_client):
    class _Boom(_FakeCompletions):
        def create(self, **kwargs):
            self.calls.append(dict(kwargs))
            raise RuntimeError("rate limited")

    completions = fake_client(_Boom())

    # Fails closed to "" (callers then use the deterministic path), no retry.
    assert llm.chat_completion("hi") == ""
    assert len(completions.calls) == 1


def test_returns_empty_without_a_key(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    assert llm.chat_completion("hi") == ""


def test_client_is_time_bounded(monkeypatch):
    """A stalled request must not hang the Gradio queue forever.

    ``llm._client`` passes the timeout and a single retry to the SDK, so a dead
    connection surfaces as ``""`` (deterministic fallback) instead of an
    indefinitely spinning "processing" state in the UI.
    """
    import openai

    captured: dict = {}

    class _CapturingOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(openai, "OpenAI", _CapturingOpenAI)
    monkeypatch.setattr(llm, "get_settings", lambda: _stub_settings())

    llm._client()

    assert captured["timeout"] == llm.REQUEST_TIMEOUT
    assert captured["max_retries"] == llm.MAX_RETRIES
    assert llm.REQUEST_TIMEOUT > 0
    assert llm.MAX_RETRIES <= 1


def _stub_settings():
    """Minimal settings object with just what ``_client`` reads."""
    return type(
        "S",
        (),
        {"openai_api_key": "sk-test", "openai_base_url": None, "openai_model": "m"},
    )()
