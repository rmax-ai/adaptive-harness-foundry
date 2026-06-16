"""Unit tests for processor implementations."""

from __future__ import annotations

import pytest

from harness_foundry.processors.base import LifecycleHook, ProcessorContext, ProcessorEvent
from harness_foundry.processors.context import ContextBudgetProcessor
from harness_foundry.processors.control import (
    RepeatedToolCallProcessor,
    StepBudgetProcessor,
)
from harness_foundry.processors.observability import CitationRequirementProcessor
from harness_foundry.processors.tools import (
    DryRunEnforcementProcessor,
    ToolAllowlistProcessor,
)


def _context(
    hook: LifecycleHook,
    *,
    state: dict[str, object] | None = None,
) -> ProcessorContext:
    return ProcessorContext(
        hook=hook,
        agent_name="support-agent",
        task_id="task-1",
        harness_id="harness-1",
        state=dict(state or {}),
    )


@pytest.mark.asyncio
async def test_dry_run_enforcement_adds_dry_run_argument() -> None:
    processor = DryRunEnforcementProcessor({"dry_run_tools": ["escalate_incident"]})

    result = await processor.process(
        _context(LifecycleHook.BEFORE_TOOL),
        ProcessorEvent(
            hook=LifecycleHook.BEFORE_TOOL,
            data={
                "tool_name": "escalate_incident",
                "tool_arguments": {
                    "customer_id": "cust-1",
                    "issue_type": "charge dispute",
                    "severity": "high",
                    "summary": "duplicate charge",
                },
            },
        ),
    )

    assert result.tool_args_mod is not None
    assert result.tool_args_mod["dry_run"] is True


@pytest.mark.asyncio
async def test_tool_allowlist_blocks_unknown_tool() -> None:
    processor = ToolAllowlistProcessor(allowed_tools=["get_customer"])

    result = await processor.process(
        _context(LifecycleHook.BEFORE_TOOL),
        ProcessorEvent(
            hook=LifecycleHook.BEFORE_TOOL,
            data={"tool_name": "delete_customer", "tool_arguments": {}},
        ),
    )

    assert result.block is True
    assert result.validation_failure is not None
    assert "delete_customer" in result.validation_failure


@pytest.mark.asyncio
async def test_step_budget_terminates_at_maximum_steps() -> None:
    processor = StepBudgetProcessor({"maximum_steps": 8})

    result = await processor.process(
        _context(LifecycleHook.STEP_END, state={"harness:step_count": 8}),
        ProcessorEvent(hook=LifecycleHook.STEP_END, data={}),
    )

    assert result.terminate is True
    assert result.validation_failure is not None


@pytest.mark.asyncio
async def test_repeated_tool_call_detects_duplicates() -> None:
    processor = RepeatedToolCallProcessor({"threshold": 2})
    event = ProcessorEvent(
        hook=LifecycleHook.AFTER_TOOL,
        data={
            "tool_name": "get_customer",
            "tool_arguments": {"customer_id": "cust-1"},
        },
    )

    first = await processor.process(
        _context(LifecycleHook.AFTER_TOOL, state={}),
        event,
    )
    second = await processor.process(
        _context(
            LifecycleHook.AFTER_TOOL,
            state={"harness:tool_call_counts": first.state_delta["harness:tool_call_counts"]},
        ),
        event,
    )

    assert first.terminate is False
    assert second.terminate is True
    assert second.validation_failure is not None


@pytest.mark.asyncio
async def test_context_budget_respects_max_items() -> None:
    processor = ContextBudgetProcessor({"max_items": 12})

    within_budget = await processor.process(
        _context(LifecycleHook.BEFORE_MODEL, state={"harness:context_items": list(range(12))}),
        ProcessorEvent(hook=LifecycleHook.BEFORE_MODEL, data={}),
    )
    over_budget = await processor.process(
        _context(LifecycleHook.BEFORE_MODEL, state={"harness:context_items": list(range(13))}),
        ProcessorEvent(hook=LifecycleHook.BEFORE_MODEL, data={}),
    )

    assert within_budget.metadata == {"context_items": 12, "warning": None}
    assert over_budget.metadata is not None
    assert "exceeded" in str(over_budget.metadata["warning"])


@pytest.mark.asyncio
async def test_citation_requirement_checks_pol_prefix() -> None:
    processor = CitationRequirementProcessor({"required_prefix": "POL-"})

    passing = await processor.process(
        _context(LifecycleHook.TASK_END, state={"harness:final_response": "See POL-REFUND-03."}),
        ProcessorEvent(hook=LifecycleHook.TASK_END, data={}),
    )
    failing = await processor.process(
        _context(LifecycleHook.TASK_END, state={"harness:final_response": "Refund is allowed."}),
        ProcessorEvent(hook=LifecycleHook.TASK_END, data={}),
    )

    assert passing.validation_failure is None
    assert failing.validation_failure is not None
