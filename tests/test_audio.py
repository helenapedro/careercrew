"""Tests for the audio module (no real API calls; OpenAI is mocked)."""

from __future__ import annotations

import os

from careercrew import audio, config


def test_audio_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config.reset_settings_cache()
    assert audio.audio_available() is False
    assert audio.transcribe("nonexistent.mp3") == ""
    assert audio.speak("hello") is None


def test_transcribe_missing_path_returns_empty():
    assert audio.transcribe(None) == ""
    assert audio.transcribe("") == ""


def test_transcribe_with_mocked_client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config.reset_settings_cache()

    class _FakeTranscriptions:
        def create(self, model, file):  # noqa: A002 - mirror the SDK kwarg
            return type("R", (), {"text": "  I built an API.  "})()

    class _FakeClient:
        audio = type("A", (), {"transcriptions": _FakeTranscriptions()})()

    monkeypatch.setattr(audio, "_client", lambda: _FakeClient())
    clip = tmp_path / "answer.mp3"
    clip.write_bytes(b"fake-audio")
    assert audio.transcribe(str(clip)) == "I built an API."


def test_speak_with_mocked_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config.reset_settings_cache()

    class _FakeSpeech:
        def create(self, model, voice, input):  # noqa: A002 - mirror the SDK kwarg
            return type("R", (), {"write_to_file": lambda self, path: open(path, "wb").close()})()

    class _FakeClient:
        audio = type("A", (), {"speech": _FakeSpeech()})()

    monkeypatch.setattr(audio, "_client", lambda: _FakeClient())
    path = audio.speak("Tell me about yourself.")
    assert path is not None
    os.unlink(path)


def test_speak_returns_none_on_client_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config.reset_settings_cache()

    def _boom():
        raise RuntimeError("no network")

    monkeypatch.setattr(audio, "_client", _boom)
    assert audio.speak("hello") is None
