"""Trace schema models for harness execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from harness_foundry.schema.processor import LifecycleHook


class TokenUsage(BaseModel):
    """Token accounting for a model invocation."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)


class ErrorRecord(BaseModel):
    """Structured error persisted in trace output."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    details: dict[str, Any] | None = None


class TraceEvent(BaseModel):
    """Normalized trace event emitted for a lifecycle hook."""

    model_config = ConfigDict(frozen=True)

    trace_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    harness_id: str = Field(..., min_length=1)
    harness_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    variant_id: str | None = None
    sequence_number: int = Field(..., ge=0)
    timestamp: datetime
    hook: LifecycleHook
    event_type: str = Field(..., min_length=1)
    agent_name: str | None = None
    processor_name: str | None = None
    input_summary: dict[str, Any] | None = None
    output_summary: dict[str, Any] | None = None
    state_delta: dict[str, Any] | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: Any | None = None
    model_name: str | None = None
    token_usage: TokenUsage | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    error: ErrorRecord | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceRun(BaseModel):
    """Run-level metadata for a benchmark or evaluation execution."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(..., min_length=1)
    harness_id: str = Field(..., min_length=1)
    harness_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    split: str = Field(..., min_length=1)
    started_at: datetime
    completed_at: datetime | None = None
    task_count: int = Field(..., ge=0)
