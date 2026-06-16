"""Control-flow processor implementations."""

from __future__ import annotations

import json
from typing import ClassVar

from harness_foundry.processors.base import (
    BaseProcessor,
    LifecycleHook,
    ProcessorCapability,
    ProcessorContext,
    ProcessorEvent,
    ProcessorResult,
)


class StepBudgetProcessor(BaseProcessor):
    """Terminate execution when the configured step budget is exhausted."""

    name = "step_budget"
    version = "1.0.0"
    hook = LifecycleHook.STEP_END
    description = "Terminates the task when step count reaches the configured maximum."
    config_schema: ClassVar[dict[str, object]] = {
        "maximum_steps": {"type": "integer", "minimum": 1}
    }
    declared_reads: ClassVar[set[str]] = {"harness:step_count"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {
        ProcessorCapability.TERMINATE,
        ProcessorCapability.METADATA,
    }

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        maximum_steps = int(self.config.get("maximum_steps", 8))
        step_count = int(context.state.get("harness:step_count", 0))
        if step_count < maximum_steps:
            return ProcessorResult(metadata={"step_count": step_count})

        return ProcessorResult(
            terminate=True,
            validation_failure=f"Step budget exhausted at {step_count} steps.",
            metadata={"step_count": step_count, "maximum_steps": maximum_steps},
        )


class RepeatedToolCallProcessor(BaseProcessor):
    """Terminate repeated identical tool calls in the same task."""

    name = "repeated_tool_call"
    version = "1.0.0"
    hook = LifecycleHook.AFTER_TOOL
    description = "Detects identical repeated tool calls and terminates when a threshold is met."
    config_schema: ClassVar[dict[str, object]] = {"threshold": {"type": "integer", "minimum": 1}}
    declared_reads: ClassVar[set[str]] = {"harness:tool_call_counts"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {
        ProcessorCapability.STATE,
        ProcessorCapability.TERMINATE,
        ProcessorCapability.METADATA,
    }

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        threshold = int(self.config.get("threshold", 2))
        tool_name = str(event.data.get("tool_name", "")).strip()
        tool_arguments = dict(event.data.get("tool_arguments", {}))
        signature = json.dumps(
            {"tool_name": tool_name, "tool_arguments": tool_arguments},
            sort_keys=True,
            separators=(",", ":"),
        )
        call_counts = dict(context.state.get("harness:tool_call_counts", {}))
        count = int(call_counts.get(signature, 0)) + 1
        call_counts[signature] = count
        terminate = count >= threshold
        return ProcessorResult(
            state_delta={"harness:tool_call_counts": call_counts},
            metadata={"tool_name": tool_name, "repeat_count": count},
            terminate=terminate,
            validation_failure=(
                f"Repeated tool call threshold reached for {tool_name}." if terminate else None
            ),
        )
