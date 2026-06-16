"""Grounding processor implementations."""

from __future__ import annotations

from typing import ClassVar

from harness_foundry.processors.base import (
    BaseProcessor,
    LifecycleHook,
    ProcessorCapability,
    ProcessorContext,
    ProcessorEvent,
    ProcessorResult,
)


class GroundingCaptureProcessor(BaseProcessor):
    """Capture top-level tool result facts into session state."""

    name = "grounding_capture"
    version = "1.0.0"
    hook = LifecycleHook.AFTER_TOOL
    description = "Stores tool result facts for later grounding checks."
    declared_reads: ClassVar[set[str]] = {"harness:grounding:facts"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
    }

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        tool_result = event.data.get("tool_result", {})
        if not isinstance(tool_result, dict) or not tool_result:
            return ProcessorResult()

        existing_facts = dict(context.state.get("harness:grounding:facts", {}))
        existing_facts.update(tool_result)
        return ProcessorResult(
            state_delta={"harness:grounding:facts": existing_facts},
            metadata={"captured_fact_keys": list(tool_result)},
        )


class GroundingCheckProcessor(BaseProcessor):
    """Check that required facts are grounded in tool outputs."""

    name = "grounding_check"
    version = "1.0.0"
    hook = LifecycleHook.TASK_END
    description = "Validates that required answer facts were observed in grounded tool output."
    config_schema: ClassVar[dict[str, object]] = {"required_fact_keys": {"type": "array"}}
    declared_reads: ClassVar[set[str]] = {"harness:grounding:facts"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {ProcessorCapability.METADATA}

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        required_fact_keys = list(self.config.get("required_fact_keys", []))
        grounded_facts = context.state.get("harness:grounding:facts", {})
        if not isinstance(grounded_facts, dict):
            grounded_facts = {}

        missing = [key for key in required_fact_keys if key not in grounded_facts]
        return ProcessorResult(
            metadata={"missing_fact_keys": missing, "grounded_fact_keys": list(grounded_facts)},
            validation_failure=(
                f"Missing grounded facts: {', '.join(missing)}" if missing else None
            ),
        )
