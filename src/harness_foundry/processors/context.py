"""Context-oriented processor implementations."""

from __future__ import annotations

from typing import Any, ClassVar

from harness_foundry.processors.base import (
    BaseProcessor,
    LifecycleHook,
    ProcessorCapability,
    ProcessorContext,
    ProcessorEvent,
    ProcessorResult,
)


class TaskFamilyContextProcessor(BaseProcessor):
    """Attach task-family-specific instructions to session state."""

    name = "task_family_context"
    version = "1.0.0"
    hook = LifecycleHook.TASK_START
    description = "Adds family-specific instruction text to the processor state."
    config_schema: ClassVar[dict[str, object]] = {"instructions": {"type": "object"}}
    declared_reads: ClassVar[set[str]] = {
        "harness:family",
        "harness:agent:instruction_append",
    }
    declared_writes: ClassVar[set[ProcessorCapability]] = {ProcessorCapability.STATE}

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        family = str(context.state.get("harness:family", "")).strip()
        instructions = self.config.get("instructions", {})
        family_instruction = instructions.get(family)
        if not family_instruction:
            return ProcessorResult()

        existing = str(context.state.get("harness:agent:instruction_append", "")).strip()
        updated = f"{existing}\n\n{family_instruction}" if existing else str(family_instruction)
        return ProcessorResult(
            state_delta={"harness:agent:instruction_append": updated},
        )


class RelevantFixtureContextProcessor(BaseProcessor):
    """Promote a bounded subset of fixture data into explicit session keys."""

    name = "relevant_fixture_context"
    version = "1.0.0"
    hook = LifecycleHook.BEFORE_MODEL
    description = "Injects the most relevant fixture values into session state."
    config_schema: ClassVar[dict[str, object]] = {"max_fixtures": {"type": "integer", "minimum": 1}}
    declared_reads: ClassVar[set[str]] = {"harness:task_id", "harness:fixture_state"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
    }

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        fixture_state = context.state.get("harness:fixture_state", {})
        if not isinstance(fixture_state, dict) or not fixture_state:
            return ProcessorResult()

        max_fixtures = int(self.config.get("max_fixtures", 3))
        selected_items = list(fixture_state.items())[:max_fixtures]
        state_delta = {f"harness:fixture:{key}": value for key, value in selected_items}
        return ProcessorResult(
            state_delta=state_delta,
            metadata={
                "task_id": context.state.get("harness:task_id", context.task_id),
                "selected_fixture_keys": [key for key, _ in selected_items],
            },
        )


class ContextBudgetProcessor(BaseProcessor):
    """Emit metadata warnings when session context grows too large."""

    name = "context_budget"
    version = "1.0.0"
    hook = LifecycleHook.BEFORE_MODEL
    description = "Warns when the processor-visible context budget is exceeded."
    config_schema: ClassVar[dict[str, object]] = {"max_items": {"type": "integer", "minimum": 1}}
    declared_reads: ClassVar[set[str]] = {"harness:context_items", "harness:context_size"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {ProcessorCapability.METADATA}

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        max_items = int(self.config.get("max_items", 12))
        context_size = _context_size(context.state)
        if context_size <= max_items:
            return ProcessorResult(metadata={"context_items": context_size, "warning": None})

        return ProcessorResult(
            metadata={
                "context_items": context_size,
                "warning": f"context budget exceeded: {context_size} > {max_items}",
            }
        )


def _context_size(state: dict[str, Any]) -> int:
    """Estimate context size from explicit counters or session contents."""

    explicit_items = state.get("harness:context_items")
    if isinstance(explicit_items, dict | list | tuple | set):
        return len(explicit_items)
    if isinstance(explicit_items, int):
        return explicit_items

    explicit_size = state.get("harness:context_size")
    if isinstance(explicit_size, int):
        return explicit_size

    return sum(
        1
        for key in state
        if key.startswith("harness:fixture:") or key.startswith("harness:grounding:")
    )
