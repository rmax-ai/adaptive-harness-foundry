"""Unit tests for harness and schema models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_foundry.schema.harness import (
    HarnessDefinition,
    HarnessLoader,
    ProcessorInstance,
    VariantDefinition,
)
from harness_foundry.schema.processor import LifecycleHook


def build_harness_payload() -> dict:
    """Create a valid harness payload for tests."""

    return {
        "id": "baseline-harness",
        "version": "1.0.0",
        "parent_version": None,
        "author": "human",
        "task_family": "default",
        "status": "active",
        "model": {
            "provider": "google",
            "model": "gemini-2.5-flash",
        },
        "agent": {
            "name": "baseline-agent",
            "instruction": "Answer the user accurately.",
            "maximum_steps": 4,
        },
        "tools": {
            "allow": ["lookup_account"],
        },
        "processors": {
            "TASK_START": [
                {
                    "type": "task-family-context",
                    "version": "1.0.0",
                    "config": {"family": "default"},
                }
            ],
            "BEFORE_TOOL": [
                {
                    "type": "tool-allowlist",
                    "version": "1.0.0",
                    "config": {},
                }
            ],
        },
    }


def test_harness_definition_validation() -> None:
    """Harness definitions should validate strongly typed fields."""

    harness = HarnessDefinition.model_validate(build_harness_payload())

    assert harness.id == "baseline-harness"
    assert harness.processors[LifecycleHook.TASK_START][0].type == "task-family-context"
    assert harness.agent.maximum_steps == 4


def test_harness_definition_rejects_invalid_id() -> None:
    """Harness ids should enforce the slug pattern."""

    payload = build_harness_payload()
    payload["id"] = "Invalid Harness"

    with pytest.raises(ValidationError):
        HarnessDefinition.model_validate(payload)


def test_model_config_defaults() -> None:
    """Model configuration should apply default generation settings."""

    harness = HarnessDefinition.model_validate(build_harness_payload())

    assert harness.model.temperature == 0.0
    assert harness.model.maximum_output_tokens == 1024


def test_variant_definition_resolves_inheritance() -> None:
    """Variant overrides should extend the base harness without mutation."""

    base = HarnessDefinition.model_validate(build_harness_payload())
    variant = VariantDefinition.model_validate(
        {
            "harness_id": "baseline-harness",
            "version": "1.0.0",
            "task_family": "incident-triage",
            "overrides": {
                "agent": {
                    "instruction_append": "Escalate urgent incidents quickly.",
                },
                "processors": {
                    "add_per_hook": {
                        "AFTER_TOOL": [
                            {
                                "type": "citation-capture",
                                "version": "1.1.0",
                                "config": {"required": True},
                            }
                        ]
                    }
                },
            },
        }
    )

    resolved = variant.resolve(base)

    assert resolved.task_family == "incident-triage"
    assert resolved.agent.instruction_append == "Escalate urgent incidents quickly."
    assert resolved.processors[LifecycleHook.AFTER_TOOL] == [
        ProcessorInstance(
            type="citation-capture",
            version="1.1.0",
            config={"required": True},
        )
    ]
    assert base.task_family == "default"
    assert base.agent.instruction_append is None


def test_harness_loader_loads_yaml(tmp_path: Path) -> None:
    """HarnessLoader should load and validate YAML files."""

    path = tmp_path / "harness.yaml"
    path.write_text(
        """
id: baseline-harness
version: 1.0.0
parent_version: null
author: human
task_family: default
status: active
model:
  provider: google
  model: gemini-2.5-flash
agent:
  name: baseline-agent
  instruction: Answer the user accurately.
  maximum_steps: 4
tools:
  allow:
    - lookup_account
processors:
  TASK_START:
    - type: task-family-context
      version: 1.0.0
      config:
        family: default
""".strip(),
        encoding="utf-8",
    )

    harness = HarnessLoader.load(path)

    assert harness.id == "baseline-harness"
    assert harness.model.model == "gemini-2.5-flash"
