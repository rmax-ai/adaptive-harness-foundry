"""Deterministic promotion gate for evolved harness candidates."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from harness_foundry.evaluation import BenchmarkReport


class PromotionPolicy(BaseModel):
    """Thresholds used by the promotion gate."""

    model_config = ConfigDict(frozen=True)

    minimum_target_gain: float = 0.10
    maximum_overall_regression: float = 0.02
    maximum_family_regression: float = 0.05
    critical_task_regressions_allowed: int = 0
    maximum_latency_increase: float = 0.20
    maximum_token_increase: float = 0.25
    require_human_approval: bool = True


class GateCheck(BaseModel):
    """Single deterministic gate check outcome."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: str


class GateResult(BaseModel):
    """Aggregate promotion gate outcome."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    checks: list[GateCheck]


class PromotionGate:
    """Deterministic gate evaluation for evolved candidates."""

    def __init__(self, policy: PromotionPolicy | None = None):
        self._policy = policy or PromotionPolicy()

    def evaluate(
        self,
        baseline: BenchmarkReport,
        candidate: BenchmarkReport,
        policy: PromotionPolicy | None = None,
        simulate_approval: bool = False,
    ) -> GateResult:
        """Deterministically evaluate whether a candidate can be promoted."""

        active_policy = policy or self._policy
        checks = [
            self._target_gain_check(baseline, candidate, active_policy),
            self._overall_regression_check(baseline, candidate, active_policy),
            self._family_regression_check(baseline, candidate, active_policy),
            self._critical_task_check(baseline, candidate, active_policy),
            self._latency_check(baseline, candidate, active_policy),
            self._token_check(baseline, candidate, active_policy),
            self._human_approval_check(active_policy, simulate_approval),
        ]
        return GateResult(passed=all(check.passed for check in checks), checks=checks)

    def _target_gain_check(
        self,
        baseline: BenchmarkReport,
        candidate: BenchmarkReport,
        policy: PromotionPolicy,
    ) -> GateCheck:
        delta = round(candidate.total_score - baseline.total_score, 4)
        return GateCheck(
            name="minimum_target_gain",
            passed=delta >= policy.minimum_target_gain,
            detail=(
                f"Candidate total score delta={delta:.4f}; "
                f"required>={policy.minimum_target_gain:.4f}."
            ),
        )

    def _overall_regression_check(
        self,
        baseline: BenchmarkReport,
        candidate: BenchmarkReport,
        policy: PromotionPolicy,
    ) -> GateCheck:
        delta = round(candidate.total_score - baseline.total_score, 4)
        return GateCheck(
            name="maximum_overall_regression",
            passed=delta >= -policy.maximum_overall_regression,
            detail=(
                f"Candidate overall delta={delta:.4f}; "
                f"minimum allowed={-policy.maximum_overall_regression:.4f}."
            ),
        )

    def _family_regression_check(
        self,
        baseline: BenchmarkReport,
        candidate: BenchmarkReport,
        policy: PromotionPolicy,
    ) -> GateCheck:
        worst_delta = 0.0
        worst_family = "none"
        families = sorted(set(baseline.scores_by_family) | set(candidate.scores_by_family))
        for family in families:
            baseline_score = (
                baseline.scores_by_family[family].total_score
                if family in baseline.scores_by_family
                else 0.0
            )
            candidate_score = (
                candidate.scores_by_family[family].total_score
                if family in candidate.scores_by_family
                else 0.0
            )
            delta = round(candidate_score - baseline_score, 4)
            if delta < worst_delta:
                worst_delta = delta
                worst_family = family
        return GateCheck(
            name="maximum_family_regression",
            passed=worst_delta >= -policy.maximum_family_regression,
            detail=(
                f"Worst family delta={worst_delta:.4f} for {worst_family}; "
                f"minimum allowed={-policy.maximum_family_regression:.4f}."
            ),
        )

    def _critical_task_check(
        self,
        baseline: BenchmarkReport,
        candidate: BenchmarkReport,
        policy: PromotionPolicy,
    ) -> GateCheck:
        baseline_by_task = {score.task_id: score for score in baseline.scores}
        candidate_by_task = {score.task_id: score for score in candidate.scores}

        regressions = 0
        regressed_tasks: list[str] = []
        for task_id, baseline_score in baseline_by_task.items():
            if not self._is_critical_task(task_id):
                continue
            candidate_score = candidate_by_task.get(task_id)
            if candidate_score is None:
                regressions += 1
                regressed_tasks.append(task_id)
                continue
            if baseline_score.passed and not candidate_score.passed:
                regressions += 1
                regressed_tasks.append(task_id)

        return GateCheck(
            name="critical_task_regressions",
            passed=regressions <= policy.critical_task_regressions_allowed,
            detail=(
                f"Critical regressions={regressions}; "
                f"allowed<={policy.critical_task_regressions_allowed}; "
                f"tasks={','.join(regressed_tasks) or 'none'}."
            ),
        )

    def _latency_check(
        self,
        baseline: BenchmarkReport,
        candidate: BenchmarkReport,
        policy: PromotionPolicy,
    ) -> GateCheck:
        baseline_latency = self._metric_average(baseline, "latency")
        candidate_latency = self._metric_average(candidate, "latency")
        increase = self._relative_increase(baseline_latency, candidate_latency)
        return GateCheck(
            name="maximum_latency_increase",
            passed=increase <= policy.maximum_latency_increase,
            detail=(
                f"Latency increase={increase:.4f}; "
                f"allowed<={policy.maximum_latency_increase:.4f}."
            ),
        )

    def _token_check(
        self,
        baseline: BenchmarkReport,
        candidate: BenchmarkReport,
        policy: PromotionPolicy,
    ) -> GateCheck:
        baseline_tokens = self._metric_average(baseline, "tokens")
        candidate_tokens = self._metric_average(candidate, "tokens")
        increase = self._relative_increase(baseline_tokens, candidate_tokens)
        return GateCheck(
            name="maximum_token_increase",
            passed=increase <= policy.maximum_token_increase,
            detail=(
                f"Token increase={increase:.4f}; "
                f"allowed<={policy.maximum_token_increase:.4f}."
            ),
        )

    def _human_approval_check(
        self,
        policy: PromotionPolicy,
        simulate_approval: bool,
    ) -> GateCheck:
        if not policy.require_human_approval:
            return GateCheck(
                name="human_approval",
                passed=True,
                detail="Human approval not required by policy.",
            )
        return GateCheck(
            name="human_approval",
            passed=simulate_approval,
            detail="Human approval simulated." if simulate_approval else "Human approval required.",
        )

    def _metric_average(self, report: BenchmarkReport, metric_name: str) -> float:
        values: list[float] = []
        pattern = re.compile(rf"{metric_name}:(\d+(?:\.\d+)?)")
        for score in report.scores:
            for evidence in score.evidence:
                match = pattern.search(evidence)
                if match:
                    values.append(float(match.group(1)))
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _relative_increase(self, baseline_value: float, candidate_value: float) -> float:
        if baseline_value <= 0:
            return 0.0 if candidate_value <= 0 else 1.0
        return round((candidate_value - baseline_value) / baseline_value, 4)

    def _is_critical_task(self, task_id: str) -> bool:
        normalized = task_id.lower()
        return normalized.startswith("critical-") or "critical" in normalized
