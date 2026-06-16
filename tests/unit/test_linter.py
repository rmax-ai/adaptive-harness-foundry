"""Unit tests for evolution patch linting."""

from __future__ import annotations

from harness_foundry.evolution import PatchLinter
from harness_foundry.schema import (
    AgentConfig,
    HarnessDefinition,
    HarnessPatch,
    ModelConfig,
    ToolPolicy,
)


def _build_harness() -> HarnessDefinition:
    return HarnessDefinition(
        id="support-harness",
        version="1.0.0",
        parent_version=None,
        author="human",
        task_family="default",
        status="active",
        model=ModelConfig(provider="google", model="gemini-2.0-flash"),
        agent=AgentConfig(
            name="support_agent",
            instruction="Help the user.",
            instruction_append=None,
            maximum_steps=4,
        ),
        tools=ToolPolicy(allow=["get_customer"]),
        processors={},
    )


def test_linter_rejects_benchmark_task_ids() -> None:
    harness = _build_harness()
    patch = HarnessPatch(
        operation="update_agent_instruction",
        target="instruction_append",
        before=None,
        after="Mention evo-acct-001 when responding.",
        rationale="Tune for evo-acct-001.",
        predicted_benefit="Higher score.",
    )

    violations = PatchLinter().lint(patch, harness)

    assert "Patch references benchmark task IDs." in violations


def test_linter_rejects_tool_permission_expansion() -> None:
    harness = _build_harness()
    patch = HarnessPatch(
        operation="update_tool_policy",
        target="tools.allow",
        before=["get_customer"],
        after=["get_customer", "search_policy"],
        rationale="Allow more tools.",
        predicted_benefit="Better retrieval.",
    )

    violations = PatchLinter().lint(patch, harness)

    assert "Patch expands the tool allowlist." in violations


def test_linter_rejects_tracing_disable_attempts() -> None:
    harness = _build_harness()
    patch = HarnessPatch(
        operation="update_processor_config",
        target="AFTER_TOOL:observability",
        before={"enabled": True},
        after={"tracing_enabled": False},
        rationale="Reduce log volume by disabling tracing.",
        predicted_benefit="Lower overhead.",
    )

    violations = PatchLinter().lint(patch, harness)

    assert "Patch attempts to disable tracing or observability." in violations
