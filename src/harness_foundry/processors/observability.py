"""Observability and output-validation processors."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

from harness_foundry.processors.base import (
    BaseProcessor,
    LifecycleHook,
    ProcessorCapability,
    ProcessorContext,
    ProcessorEvent,
    ProcessorResult,
)


class TraceRecorderProcessor(BaseProcessor):
    """Record lightweight trace events in session state for every hook."""

    name = "trace_recorder"
    version = "1.0.0"
    hook = LifecycleHook.TASK_START
    description = "Stores normalized trace events for every lifecycle hook."
    declared_reads: ClassVar[set[str]] = {
        "harness:trace:events",
        "harness:trace:sequence",
    }
    declared_writes: ClassVar[set[ProcessorCapability]] = {ProcessorCapability.STATE}

    @classmethod
    def hooks(cls) -> tuple[LifecycleHook, ...]:
        """Register the trace recorder for every supported lifecycle hook."""

        return tuple(LifecycleHook)

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        existing_events = list(context.state.get("harness:trace:events", []))
        next_sequence = int(context.state.get("harness:trace:sequence", 0)) + 1
        trace_event = {
            "trace_id": str(uuid4()),
            "run_id": str(context.state.get("harness:run_id", "runtime")),
            "task_id": context.task_id,
            "harness_id": context.harness_id,
            "harness_version": str(context.state.get("harness:version", "0.0.0")),
            "variant_id": context.variant_id,
            "sequence_number": next_sequence,
            "timestamp": datetime.now(UTC).isoformat(),
            "hook": context.hook.value,
            "event_type": str(event.data.get("event_type", context.hook.value.casefold())),
            "agent_name": context.agent_name,
            "input_summary": _summary_for_hook(context.hook, event.data),
            "output_summary": None,
            "state_delta": None,
            "tool_name": event.data.get("tool_name"),
            "tool_arguments": event.data.get("tool_arguments"),
            "tool_result": event.data.get("tool_result"),
            "model_name": event.data.get("model"),
            "metadata": {"processor": self.name},
        }
        existing_events.append(trace_event)
        return ProcessorResult(
            state_delta={
                "harness:trace:sequence": next_sequence,
                "harness:trace:events": existing_events,
            }
        )


class CitationRequirementProcessor(BaseProcessor):
    """Validate that final responses include the required citation prefix."""

    name = "citation_requirement"
    version = "1.0.0"
    hook = LifecycleHook.TASK_END
    description = "Checks the final answer for required citation prefixes."
    config_schema: ClassVar[dict[str, object]] = {"required_prefix": {"type": "string"}}
    declared_reads: ClassVar[set[str]] = {"harness:final_response"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {ProcessorCapability.METADATA}

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        required_prefix = str(self.config.get("required_prefix", "POL-")).strip()
        response_text = _extract_response_text(context.state, event.data)
        if required_prefix and required_prefix in response_text:
            return ProcessorResult(metadata={"required_prefix": required_prefix})

        return ProcessorResult(
            metadata={"required_prefix": required_prefix},
            validation_failure=(
                f"Final response is missing a citation with prefix {required_prefix}."
            ),
        )


class StructuredFinalAnswerProcessor(BaseProcessor):
    """Validate an optional structured final response schema."""

    name = "structured_final_answer"
    version = "1.0.0"
    hook = LifecycleHook.TASK_END
    description = "Validates a JSON final answer against a minimal required-key schema."
    config_schema: ClassVar[dict[str, object]] = {"schema": {"type": ["object", "null"]}}
    declared_reads: ClassVar[set[str]] = {"harness:final_response"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {ProcessorCapability.METADATA}

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        schema = self.config.get("schema")
        if schema is None:
            return ProcessorResult()

        response_text = _extract_response_text(context.state, event.data)
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            return ProcessorResult(validation_failure="Final response is not valid JSON.")

        required_keys = list(schema.get("required", [])) if isinstance(schema, dict) else []
        missing = [key for key in required_keys if key not in parsed]
        return ProcessorResult(
            metadata={"required_keys": required_keys, "missing_keys": missing},
            validation_failure=(
                f"Final response is missing required keys: {', '.join(missing)}"
                if missing
                else None
            ),
        )


def _extract_response_text(state: dict[str, Any], event_data: dict[str, Any]) -> str:
    """Extract the final response text from state or hook payload."""

    if isinstance(event_data.get("agent_response"), str):
        return str(event_data["agent_response"])
    output_summary = event_data.get("output_summary")
    if isinstance(output_summary, dict) and isinstance(output_summary.get("agent_response"), str):
        return str(output_summary["agent_response"])
    return str(state.get("harness:final_response", ""))


def _summary_for_hook(hook: LifecycleHook, event_data: dict[str, Any]) -> dict[str, Any] | None:
    """Build a compact trace input summary for a lifecycle event."""

    if hook in {LifecycleHook.BEFORE_TOOL, LifecycleHook.AFTER_TOOL}:
        return {"tool_name": event_data.get("tool_name")}
    if hook in {LifecycleHook.BEFORE_MODEL, LifecycleHook.AFTER_MODEL}:
        return {"model": event_data.get("model")}
    return {"event_keys": sorted(event_data)}
