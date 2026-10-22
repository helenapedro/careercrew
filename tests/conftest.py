"""Shared pytest fixtures for the CareerCrew test suite."""

from __future__ import annotations

import os

import pytest

# Keep tests offline and isolated before any project module imports settings.
os.environ.setdefault("CAREERCREW_DB_PATH", ":memory:")
os.environ.setdefault("CAREERCREW_UPLOAD_DIR", "uploads")


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Point the uploads folder at a temp dir for the duration of a test."""
    from careercrew import config

    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    config.reset_settings_cache()
    yield tmp_path
    config.reset_settings_cache()
