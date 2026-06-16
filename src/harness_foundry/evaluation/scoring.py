"""Evaluation score models and deterministic aggregation helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from harness_foundry.schema.benchmark import TaskScore

__all__ = [
    "BenchmarkReport",
    "ComparisonDelta",
    "ComparisonReport",
    "FamilyScore",
    "TaskScore",
    "average",
]


class FamilyScore(BaseModel):
    """Aggregated score summary for a benchmark task family."""

    model_config = ConfigDict(frozen=True)

    family: str = Field(..., min_length=1)
    task_count: int = Field(..., ge=0)
    total_score: float = Field(..., ge=0)
    pass_rate: float = Field(..., ge=0)


class BenchmarkReport(BaseModel):
    """Scored benchmark run for a single harness and split."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(..., min_length=1)
    harness_id: str = Field(..., min_length=1)
    harness_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    split: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    scores: list[TaskScore] = Field(default_factory=list)
    total_score: float = Field(..., ge=0)
    pass_rate: float = Field(..., ge=0)
    scores_by_family: dict[str, FamilyScore] = Field(default_factory=dict)


class ComparisonDelta(BaseModel):
    """Delta between baseline and candidate scores for one scope."""

    model_config = ConfigDict(frozen=True)

    baseline: float
    candidate: float
    delta: float


class ComparisonReport(BaseModel):
    """Pairwise comparison between two benchmark reports."""

    model_config = ConfigDict(frozen=True)

    baseline_run_id: str = Field(..., min_length=1)
    candidate_run_id: str = Field(..., min_length=1)
    global_score: ComparisonDelta
    pass_rate: ComparisonDelta
    by_family: dict[str, ComparisonDelta] = Field(default_factory=dict)
    by_task: dict[str, ComparisonDelta] = Field(default_factory=dict)


def average(values: list[float]) -> float:
    """Return a deterministic arithmetic mean for a non-empty list."""

    if not values:
        return 0.0
    return sum(values) / len(values)
