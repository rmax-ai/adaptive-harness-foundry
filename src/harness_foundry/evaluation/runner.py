"""Benchmark runner orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import yaml  # type: ignore[import-untyped]

from harness_foundry.evaluation.evaluators import Evaluator
from harness_foundry.evaluation.scoring import BenchmarkReport, FamilyScore, average
from harness_foundry.runtime.runner import TaskRunner
from harness_foundry.schema import BenchmarkSplit, HarnessDefinition, LifecycleHook, TraceEvent
from harness_foundry.tracing.recorder import TraceRecorder


class BenchmarkRunner:
    """Run deterministic benchmark splits against a compiled harness."""

    def __init__(self, task_runner: TaskRunner, evaluator: Evaluator, tracer: TraceRecorder):
        self._task_runner = task_runner
        self._evaluator = evaluator
        self._tracer = tracer

    async def run_benchmark(
        self,
        harness: HarnessDefinition,
        split: str,
    ) -> BenchmarkReport:
        """Load benchmark tasks, execute them serially, and return a scored report."""

        benchmark_split = self._load_split(split)
        run_id = str(uuid4())
        scores = []
        family_scores: dict[str, list[float]] = {}
        family_passes: dict[str, list[bool]] = {}

        for task in benchmark_split.tasks:
            events = await self._task_runner.run_task(harness=harness, task=task, run_id=run_id)
            final_response = self._extract_final_response(events)
            score = self._evaluator.evaluate(
                task=task,
                events=events,
                agent_response=final_response,
            )
            scores.append(score)
            family_scores.setdefault(task.family, []).append(score.total_score)
            family_passes.setdefault(task.family, []).append(score.passed)

        return BenchmarkReport(
            run_id=run_id,
            harness_id=harness.id,
            harness_version=harness.version,
            split=split,
            model=harness.model.model,
            scores=scores,
            total_score=round(average([score.total_score for score in scores]), 4),
            pass_rate=round(average([1.0 if score.passed else 0.0 for score in scores]), 4),
            scores_by_family={
                family: FamilyScore(
                    family=family,
                    task_count=len(values),
                    total_score=round(average(values), 4),
                    pass_rate=round(
                        average([1.0 if passed else 0.0 for passed in family_passes[family]]),
                        4,
                    ),
                )
                for family, values in family_scores.items()
            },
        )

    def _load_split(self, split: str) -> BenchmarkSplit:
        path = Path("data") / "benchmarks" / f"{split}.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return BenchmarkSplit.model_validate(payload)

    def _extract_final_response(self, events: Sequence[TraceEvent]) -> str:
        for event in reversed(events):
            if (
                event.hook == LifecycleHook.TASK_END
                and event.output_summary is not None
                and "agent_response" in event.output_summary
            ):
                return str(event.output_summary["agent_response"])
        return ""
