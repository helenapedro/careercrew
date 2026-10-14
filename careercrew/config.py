"""CareerCrew - central configuration.

All settings are read from environment variables so the same code runs locally,
in tests, and in Docker. Secrets are never hard-coded and never logged.
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
DATA_DIR = PROJECT_ROOT / "data"
ANSWER_BANK_PATH = DATA_DIR / "answer_bank.yaml"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    upload_dir: str
    db_path: str
    max_revisions: int
    request_timeout_s: float
    fetch_timeout_s: float
    max_retries: int
    app_port: int
    log_level: str

    @property
    def has_llm(self) -> bool:
        """True when an LLM key is configured for the agents."""
        return bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
        openai_model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        upload_dir=os.getenv("CAREERCREW_UPLOAD_DIR") or "uploads",
        db_path=os.getenv("CAREERCREW_DB_PATH") or "careercrew.db",
        max_revisions=_env_int("CAREERCREW_MAX_REVISIONS", 2),
        request_timeout_s=float(os.getenv("CAREERCREW_REQUEST_TIMEOUT", "120")),
        fetch_timeout_s=float(os.getenv("CAREERCREW_FETCH_TIMEOUT", "20")),
        max_retries=_env_int("CAREERCREW_MAX_RETRIES", 2),
        app_port=_env_int("PORT", 7860),
        log_level=os.getenv("CAREERCREW_LOG_LEVEL", "INFO"),
    )


def reset_settings_cache() -> None:
    """Clear the settings cache (used by tests that mutate the environment)."""
    get_settings.cache_clear()
