"""Benchmark schema models for deterministic evaluation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkTask(BaseModel):
    """Single benchmark task with fixtures and expected outcomes."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1)
    family: str = Field(..., min_length=1)
    user_input: str = Field(..., min_length=1)
    fixture_state: dict[str, Any] = Field(default_factory=dict)
    expected_tool_calls: list[str] = Field(default_factory=list)
    forbidden_tool_calls: list[str] = Field(default_factory=list)
    expected_facts: dict[str, Any] = Field(default_factory=dict)
    required_citations: list[str] = Field(default_factory=list)
    maximum_steps: int = Field(..., ge=1)
    tags: list[str] = Field(default_factory=list)


class BenchmarkSplit(BaseModel):
    """Collection of benchmark tasks loaded from YAML."""

    model_config = ConfigDict(frozen=True)

    tasks: list[BenchmarkTask] = Field(default_factory=list)


class TaskScore(BaseModel):
    """Deterministic scorecard for a single benchmark task."""

    model_config = ConfigDict(frozen=True)

    task_id: str = Field(..., min_length=1)
    passed: bool
    total_score: float = Field(..., ge=0)
    correctness: float = Field(..., ge=0)
    tool_use: float = Field(..., ge=0)
    safety: float = Field(..., ge=0)
    grounding: float = Field(..., ge=0)
    efficiency: float = Field(..., ge=0)
    failure_codes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class HarnessPatch(BaseModel):
    """Structured configuration mutation proposed by the evolution plane."""

    model_config = ConfigDict(frozen=True)

    operation: Literal[
        "add_processor",
        "remove_processor",
        "replace_processor",
        "update_processor_config",
        "update_agent_instruction",
        "update_tool_policy",
        "create_variant",
    ]
    target: str = Field(..., min_length=1)
    before: Any | None = None
    after: Any
    rationale: str = Field(..., min_length=1)
    supporting_trace_ids: list[str] = Field(default_factory=list)
    predicted_benefit: str = Field(..., min_length=1)
    possible_regressions: list[str] = Field(default_factory=list)
