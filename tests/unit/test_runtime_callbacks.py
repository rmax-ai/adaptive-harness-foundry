"""Unit tests for runtime callback factory behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from harness_foundry.runtime.callbacks import CallbackFactory, ProcessorRegistry
from harness_foundry.schema import (
    AgentConfig,
    HarnessDefinition,
    LifecycleHook,
    ModelConfig,
    ProcessorContext,
    ProcessorEvent,
    ProcessorInstance,
    ProcessorResult,
    ToolPolicy,
)


class StubRegistry(ProcessorRegistry):
    """Minimal registry stub used to drive callback behavior."""

    async def invoke(
        self,
        instance: ProcessorInstance,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        del instance, context, event
        return ProcessorResult(
            allowed_capabilities={"STATE", "TOOL_ARGUMENTS", "BLOCK"},
            state_delta={"harness:step_count": 2},
            tool_args_mod={"customer_id": "override"},
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
        processors={LifecycleHook.BEFORE_TOOL: [ProcessorInstance(type="guard", version="1.0.0")]},
    )


@pytest.mark.asyncio
async def test_before_tool_callback_applies_processor_mutations() -> None:
    harness = _build_harness()
    factory = CallbackFactory(StubRegistry())
    callback = factory.create_before_tool_callback(
        harness.processors[LifecycleHook.BEFORE_TOOL], harness
    )

    args: dict[str, Any] = {"customer_id": "original"}
    tool_context = SimpleNamespace(state={"harness:task_id": "task-1"})
    tool = SimpleNamespace(name="get_customer")

    result = await callback(tool=tool, args=args, tool_context=tool_context)

    assert result is None
    assert args == {"customer_id": "override"}
    assert tool_context.state["harness:step_count"] == 2
