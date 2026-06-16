"""Unit tests for canonical serialization and hashing."""

from __future__ import annotations

import hashlib

from harness_foundry.schema.harness import HarnessDefinition


def build_payload() -> dict:
    """Create a stable harness payload for hashing tests."""

    return {
        "id": "hash-harness",
        "version": "1.0.0",
        "parent_version": None,
        "author": "human",
        "task_family": "default",
        "status": "draft",
        "model": {
            "provider": "google",
            "model": "gemini-2.5-flash",
            "maximum_output_tokens": 512,
            "temperature": 0.2,
        },
        "agent": {
            "name": "hash-agent",
            "instruction": "Be precise.",
            "maximum_steps": 3,
        },
        "tools": {
            "allow": ["search", "lookup"],
        },
        "processors": {},
    }


def test_canonical_json_is_stable() -> None:
    """Canonical JSON should use sorted keys and compact separators."""

    harness = HarnessDefinition.model_validate(build_payload())

    assert harness.canonical_json() == (
        '{"agent":{"instruction":"Be precise.","instruction_append":null,'
        '"maximum_steps":3,"name":"hash-agent"},"author":"human",'
        '"id":"hash-harness","model":{"maximum_output_tokens":512,'
        '"model":"gemini-2.5-flash","provider":"google","temperature":0.2},'
        '"parent_version":null,"processors":{},"status":"draft",'
        '"task_family":"default","tools":{"allow":["search","lookup"]},'
        '"version":"1.0.0"}'
    )


def test_sha256_hash_matches_canonical_json() -> None:
    """Hashing should be derived from the canonical JSON string."""

    harness = HarnessDefinition.model_validate(build_payload())
    expected = hashlib.sha256(harness.canonical_json().encode("utf-8")).hexdigest()

    assert harness.config_hash() == expected
