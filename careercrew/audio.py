"""CareerCrew - audio for the virtual mock interview.

Thin, failure-tolerant wrappers over the OpenAI audio API:

* ``transcribe`` - speech-to-text (``whisper-1``) for the candidate's answer.
* ``speak``      - text-to-speech (``tts-1``) for the interviewer's question.

Both never raise into the UI. They return ``None`` (or ``""``) and log when
audio is unavailable, so the interview can degrade to a text-only session.
``audio_available()`` reports whether audio can be attempted at all.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from careercrew.config import get_settings

logger = logging.getLogger("careercrew.audio")


def audio_available() -> bool:
    """Whether an OpenAI key is configured so audio can be attempted."""
    return get_settings().has_audio


def _client():
    from openai import OpenAI

    settings = get_settings()
    kwargs: dict = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def transcribe(audio_path: str | None) -> str:
    """Transcribe a recorded answer with ``whisper-1``.

    Returns the transcript text, or ``""`` when audio is unavailable, the path
    is missing, or transcription fails. Never raises.
    """
    if not audio_path or not os.path.isfile(str(audio_path)):
        return ""
    if not audio_available():
        logger.info("transcribe skipped: no audio-capable key")
        return ""
    settings = get_settings()
    try:
        with open(audio_path, "rb") as handle:
            result = _client().audio.transcriptions.create(
                model=settings.stt_model,
                file=handle,
            )
        return (getattr(result, "text", "") or "").strip()
    except Exception as exc:  # noqa: BLE001 - degrade to text, never crash
        logger.warning("transcription failed: %s", exc)
        return ""


def speak(text: str) -> str | None:
    """Synthesize the interviewer's question with ``tts-1``.

    Returns a path to an mp3 file, or ``None`` when audio is unavailable or
    synthesis fails. Never raises.
    """
    text = (text or "").strip()
    if not text or not audio_available():
        return None
    settings = get_settings()
    try:
        response = _client().audio.speech.create(
            model=settings.tts_model,
            voice=settings.tts_voice,
            input=text,
        )
        handle, path = tempfile.mkstemp(prefix="careercrew_q", suffix=".mp3")
        os.close(handle)
        # The SDK provides .write_to_file / .stream_to_file depending on version.
        if hasattr(response, "write_to_file"):
            response.write_to_file(path)
        else:  # pragma: no cover - older SDK shape
            with open(path, "wb") as out:
                for chunk in response.iter_bytes():
                    out.write(chunk)
        return path
    except Exception as exc:  # noqa: BLE001 - degrade to text, never crash
        logger.warning("speech synthesis failed: %s", exc)
        return None


def cleanup(path: str | None) -> None:
    """Best-effort removal of a temporary audio file."""
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
