"""Processor schema models for lifecycle integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ProcessorSpec(BaseModel):
    """Typed processor declaration registered in the catalog."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    hook: LifecycleHook
    description: str = Field(..., min_length=1)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    declared_reads: set[str] = Field(default_factory=set)
    declared_writes: set[ProcessorCapability] = Field(default_factory=set)
    exclusions: list[str] = Field(default_factory=list)
    ordering: Literal["first", "last", "normal"] = "normal"

    @model_validator(mode="after")
    def validate_declared_writes(self) -> ProcessorSpec:
        """Ensure declared writes are valid for the selected hook."""

        invalid_capabilities = self.declared_writes - HOOK_CAPABILITIES[self.hook]
        if invalid_capabilities:
            invalid = ", ".join(sorted(capability.value for capability in invalid_capabilities))
            raise ValueError(
                f"Capabilities [{invalid}] are not allowed for hook {self.hook.value}."
            )
        return self


class ProcessorResult(BaseModel):
    """Normalized result returned by a processor invocation."""

    model_config = ConfigDict(frozen=True)

    MODIFICATION_CAPABILITIES: ClassVar[dict[str, ProcessorCapability]] = {
        "state_delta": ProcessorCapability.STATE,
        "metadata": ProcessorCapability.METADATA,
        "model_request_mod": ProcessorCapability.MODEL_REQUEST,
        "model_response_mod": ProcessorCapability.MODEL_RESPONSE,
        "tool_args_mod": ProcessorCapability.TOOL_ARGUMENTS,
        "tool_result_mod": ProcessorCapability.TOOL_RESULT,
    }

    allowed_capabilities: set[str] = Field(default_factory=set)
    state_delta: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    model_request_mod: dict[str, Any] | None = None
    model_response_mod: dict[str, Any] | None = None
    tool_args_mod: dict[str, Any] | None = None
    tool_result_mod: Any | None = None
    block: bool = False
    terminate: bool = False
    validation_failure: str | None = None

    @model_validator(mode="after")
    def validate_capability_usage(self) -> ProcessorResult:
        """Validate that populated fields are permitted by allowed capabilities."""

        allowed = {ProcessorCapability(value) for value in self.allowed_capabilities}
        for field_name, capability in self.MODIFICATION_CAPABILITIES.items():
            if getattr(self, field_name) is not None and capability not in allowed:
                raise ValueError(f"Field {field_name} requires capability {capability.value}.")
        if self.block and ProcessorCapability.BLOCK not in allowed:
            raise ValueError("Field block requires capability BLOCK.")
        if self.terminate and ProcessorCapability.TERMINATE not in allowed:
            raise ValueError("Field terminate requires capability TERMINATE.")
        return self


class ProcessorContext(BaseModel):
    """Context passed to processors during lifecycle execution."""

    model_config = ConfigDict(frozen=True)

    hook: LifecycleHook
    agent_name: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    harness_id: str = Field(..., min_length=1)
    state: dict[str, Any] = Field(default_factory=dict)


class ProcessorEvent(BaseModel):
    """Hook-specific event payload supplied to a processor."""

    model_config = ConfigDict(frozen=True)

    hook: LifecycleHook
    data: dict[str, Any] = Field(default_factory=dict)
