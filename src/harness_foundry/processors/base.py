"""Base runtime types for harness processors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar


class LifecycleHook(StrEnum):
    """Lifecycle hooks exposed by the harness runtime."""

    TASK_START = "TASK_START"
    STEP_START = "STEP_START"
    BEFORE_MODEL = "BEFORE_MODEL"
    AFTER_MODEL = "AFTER_MODEL"
    BEFORE_TOOL = "BEFORE_TOOL"
    AFTER_TOOL = "AFTER_TOOL"
    STEP_END = "STEP_END"
    TASK_END = "TASK_END"


class ProcessorCapability(StrEnum):
    """Capabilities a processor may declare or consume."""

    STATE = "STATE"
    METADATA = "METADATA"
    MODEL_REQUEST = "MODEL_REQUEST"
    MODEL_RESPONSE = "MODEL_RESPONSE"
    TOOL_ARGUMENTS = "TOOL_ARGUMENTS"
    TOOL_RESULT = "TOOL_RESULT"
    BLOCK = "BLOCK"
    TERMINATE = "TERMINATE"


HOOK_CAPABILITIES: dict[LifecycleHook, set[ProcessorCapability]] = {
    LifecycleHook.TASK_START: {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
    },
    LifecycleHook.STEP_START: {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
        ProcessorCapability.TERMINATE,
    },
    LifecycleHook.BEFORE_MODEL: {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
        ProcessorCapability.MODEL_REQUEST,
        ProcessorCapability.BLOCK,
        ProcessorCapability.TERMINATE,
    },
    LifecycleHook.AFTER_MODEL: {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
        ProcessorCapability.MODEL_RESPONSE,
        ProcessorCapability.TERMINATE,
    },
    LifecycleHook.BEFORE_TOOL: {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
        ProcessorCapability.TOOL_ARGUMENTS,
        ProcessorCapability.BLOCK,
        ProcessorCapability.TERMINATE,
    },
    LifecycleHook.AFTER_TOOL: {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
        ProcessorCapability.TOOL_RESULT,
        ProcessorCapability.TERMINATE,
    },
    LifecycleHook.STEP_END: {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
        ProcessorCapability.TERMINATE,
    },
    LifecycleHook.TASK_END: {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
        ProcessorCapability.TERMINATE,
    },
}


@dataclass(slots=True)
class ProcessorContext:
    """Context available to all processors."""

    hook: LifecycleHook
    agent_name: str
    task_id: str
    harness_id: str
    variant_id: str | None = None
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessorEvent:
    """Event data passed to a processor."""

    hook: LifecycleHook
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessorResult:
    """Result from a processor execution."""

    state_delta: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    model_request_mod: dict[str, Any] | None = None
    model_response_mod: dict[str, Any] | None = None
    tool_args_mod: dict[str, Any] | None = None
    tool_result_mod: Any | None = None
    block: bool = False
    terminate: bool = False
    validation_failure: str | None = None


def validate_capabilities(
    result: ProcessorResult,
    allowed_caps: set[ProcessorCapability],
    hook: LifecycleHook,
) -> None:
    """Validate that a processor result only uses capabilities allowed for a hook."""

    modifications = {
        "state_delta": ProcessorCapability.STATE,
        "metadata": ProcessorCapability.METADATA,
        "model_request_mod": ProcessorCapability.MODEL_REQUEST,
        "model_response_mod": ProcessorCapability.MODEL_RESPONSE,
        "tool_args_mod": ProcessorCapability.TOOL_ARGUMENTS,
        "tool_result_mod": ProcessorCapability.TOOL_RESULT,
    }
    for field_name, capability in modifications.items():
        if getattr(result, field_name) is not None and capability not in allowed_caps:
            raise ValueError(
                f"{field_name} requires capability {capability.value} for hook {hook.value}."
            )
    if result.block and ProcessorCapability.BLOCK not in allowed_caps:
        raise ValueError(f"block is not allowed for hook {hook.value}.")
    if result.terminate and ProcessorCapability.TERMINATE not in allowed_caps:
        raise ValueError(f"terminate is not allowed for hook {hook.value}.")


class BaseProcessor(ABC):
    """Abstract base for all processors."""

    name: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    hook: ClassVar[LifecycleHook]
    description: ClassVar[str] = ""
    config_schema: ClassVar[dict[str, Any]] = {}
    declared_reads: ClassVar[set[str]] = set()
    declared_writes: ClassVar[set[ProcessorCapability]] = set()
    exclusions: ClassVar[list[str]] = []
    ordering: ClassVar[str] = "normal"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @classmethod
    def hooks(cls) -> tuple[LifecycleHook, ...]:
        """Return the lifecycle hooks handled by this processor."""

        return (cls.hook,)

    @classmethod
    def allowed_capabilities(cls) -> set[ProcessorCapability]:
        """Return allowed capabilities for the processor hook."""

        return set(HOOK_CAPABILITIES[cls.hook])

    @abstractmethod
    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        """Process a lifecycle event and return normalized mutations."""
