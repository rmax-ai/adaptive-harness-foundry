"""Redaction helpers for trace exports."""

from __future__ import annotations

import re
from typing import Any

SECRET_PATTERNS = [
    r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+",
    r"GOOGLE_API_KEY=.*",
    r"(?i)(token\s*[:=]\s*)[^\s,;]{8,}",
    r"(?i)(secret\s*[:=]\s*)[^\s,;]{8,}",
]

_COMPILED_SECRET_PATTERNS = [re.compile(pattern) for pattern in SECRET_PATTERNS]


def redact_secrets(text: str) -> str:
    """Replace known secret patterns in text with a redaction marker."""

    redacted = text
    for pattern in _COMPILED_SECRET_PATTERNS:
        redacted = pattern.sub(_replace_secret_match, redacted)
    return redacted


def redact_dict(data: dict) -> dict:
    """Recursively redact secret-like values from a dictionary."""

    return {key: _redact_value(value) for key, value in data.items()}


def _replace_secret_match(match: re.Match[str]) -> str:
    """Preserve a matched key prefix when present while redacting the value."""

    prefix = match.group(1) if match.lastindex else ""
    return f"{prefix}***REDACTED***"


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return redact_dict(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value
