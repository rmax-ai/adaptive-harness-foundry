"""Deterministic hashing helpers for harness configurations."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(data: dict[str, Any]) -> str:
    """Serialize a mapping to canonical JSON."""

    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def config_sha256(canonical_str: str) -> str:
    """Return the SHA-256 hash of a canonical JSON string."""

    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
