"""Comparison utilities for benchmark reports."""

from __future__ import annotations

from harness_foundry.evaluation.scoring import (
    BenchmarkReport,
    ComparisonDelta,
    ComparisonReport,
)


class ComparisonEngine:
    """Compare two benchmark reports and compute score deltas."""

    def compare(self, baseline: BenchmarkReport, candidate: BenchmarkReport) -> ComparisonReport:
        """Compare two runs, computing deltas per task, family, and globally."""

        baseline_tasks = {score.task_id: score for score in baseline.scores}
        candidate_tasks = {score.task_id: score for score in candidate.scores}
        task_ids = sorted(set(baseline_tasks) | set(candidate_tasks))

        families = sorted(set(baseline.scores_by_family) | set(candidate.scores_by_family))
        return ComparisonReport(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            global_score=self._delta(baseline.total_score, candidate.total_score),
            pass_rate=self._delta(baseline.pass_rate, candidate.pass_rate),
            by_family={
                family: self._delta(
                    baseline.scores_by_family[family].total_score
                    if family in baseline.scores_by_family
                    else 0.0,
                    candidate.scores_by_family[family].total_score
                    if family in candidate.scores_by_family
                    else 0.0,
                )
                for family in families
            },
            by_task={
                task_id: self._delta(
                    baseline_tasks[task_id].total_score if task_id in baseline_tasks else 0.0,
                    candidate_tasks[task_id].total_score if task_id in candidate_tasks else 0.0,
                )
                for task_id in task_ids
            },
        )

    def _delta(self, baseline: float, candidate: float) -> ComparisonDelta:
        return ComparisonDelta(
            baseline=round(baseline, 4),
            candidate=round(candidate, 4),
            delta=round(candidate - baseline, 4),
        )
