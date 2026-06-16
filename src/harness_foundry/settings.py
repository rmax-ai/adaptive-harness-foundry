"""Application settings sourced from environment variables."""

from __future__ import annotations

import os


def _getenv(name: str, default: str | None = None) -> str | None:
    """Return an environment variable with an optional default."""

    return os.environ.get(name, default)


GOOGLE_API_KEY = _getenv("GOOGLE_API_KEY")
GOOGLE_CLOUD_PROJECT = _getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = _getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
HARNESS_FOUNDRY_MODEL = _getenv("HARNESS_FOUNDRY_MODEL", "gemini-2.5-flash")
HARNESS_FOUNDRY_META_MODEL = _getenv("HARNESS_FOUNDRY_META_MODEL", "gemini-2.5-flash")
DATABASE_URL = _getenv("DATABASE_URL", "sqlite:///data/harness_foundry.db")
LOG_LEVEL = _getenv("LOG_LEVEL", "INFO")
