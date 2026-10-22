"""Read settings from the environment. No secrets are hard-coded.

What it does: loads API keys, model names, and folder paths.
Who calls it: every module that needs a setting, via get_settings().
What it returns: one frozen Settings object for the process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load a local .env if present (does not override real environment variables).
load_dotenv(override=False)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
RESUME_GUIDELINES_PATH = KNOWLEDGE_DIR / "resume_guidelines.md"
INTERVIEW_GUIDELINES_PATH = KNOWLEDGE_DIR / "interview_guidelines.md"
COACHING_GUIDELINES_PATH = KNOWLEDGE_DIR / "interview_guidelines.md"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of runtime configuration."""

    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str
    stt_model: str
    tts_model: str
    tts_voice: str
    interview_question_count: int
    upload_dir: str
    db_path: str
    max_revisions: int
    app_port: int
    log_level: str

    @property
    def has_llm(self) -> bool:
        """True when an LLM key is configured for the agents."""
        return bool(self.openai_api_key)

    @property
    def has_audio(self) -> bool:
        """True when audio (speech-to-text / text-to-speech) can be attempted."""
        return bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
        openai_model=os.getenv("OPENAI_MODEL") or "gpt-6-luna",
        stt_model=os.getenv("CAREERCREW_STT_MODEL") or "whisper-1",
        tts_model=os.getenv("CAREERCREW_TTS_MODEL") or "tts-1",
        tts_voice=os.getenv("CAREERCREW_TTS_VOICE") or "alloy",
        interview_question_count=_env_int("CAREERCREW_INTERVIEW_QUESTIONS", 5),
        upload_dir=os.getenv("CAREERCREW_UPLOAD_DIR") or "uploads",
        db_path=os.getenv("CAREERCREW_DB_PATH") or "careercrew.db",
        max_revisions=_env_int("CAREERCREW_MAX_REVISIONS", 2),
        app_port=_env_int("PORT", 7860),
        log_level=os.getenv("CAREERCREW_LOG_LEVEL", "INFO"),
    )


def reset_settings_cache() -> None:
    """Clear the settings cache (used by tests that mutate the environment)."""
    get_settings.cache_clear()
