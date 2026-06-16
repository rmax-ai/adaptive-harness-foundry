"""Unit tests for the deterministic promotion gate."""

from __future__ import annotations

from harness_foundry.evaluation import BenchmarkReport, FamilyScore, TaskScore
from harness_foundry.evolution import PromotionGate, PromotionPolicy


def _score(task_id: str, total_score: float, passed: bool) -> TaskScore:
    return TaskScore(
        task_id=task_id,
        passed=passed,
        total_score=total_score,
        correctness=total_score,
        tool_use=total_score,
        safety=total_score,
        grounding=total_score,
        efficiency=total_score,
        failure_codes=[] if passed else ["correctness"],
        evidence=[],
    )


def _report(total_score: float, scores: list[TaskScore]) -> BenchmarkReport:
    family_scores: dict[str, list[float]] = {}
    family_passes: dict[str, list[bool]] = {}
    for score in scores:
        family = score.task_id.split("-", 1)[0]
        family_scores.setdefault(family, []).append(score.total_score)
        family_passes.setdefault(family, []).append(score.passed)

    return BenchmarkReport(
        run_id="run-1",
        harness_id="support-harness",
        harness_version="1.0.0",
        split="evolution",
        model="gemini-2.0-flash",
        scores=scores,
        total_score=total_score,
        pass_rate=sum(1.0 if score.passed else 0.0 for score in scores) / len(scores),
        scores_by_family={
            family: FamilyScore(
                family=family,
                task_count=len(values),
                total_score=sum(values) / len(values),
                pass_rate=sum(1.0 if passed else 0.0 for passed in family_passes[family])
                / len(values),
            )
            for family, values in family_scores.items()
        },
    )


def test_promotion_gate_passes_candidate_with_target_gain() -> None:
    gate = PromotionGate(
        PromotionPolicy(require_human_approval=False, minimum_target_gain=0.10)
    )
    baseline = _report(0.60, [_score("policy-001", 0.60, False), _score("policy-002", 0.60, True)])
    candidate = _report(0.75, [_score("policy-001", 0.75, True), _score("policy-002", 0.75, True)])

    result = gate.evaluate(baseline, candidate)

    assert result.passed is True


def test_promotion_gate_fails_candidate_with_overall_regression() -> None:
    gate = PromotionGate(
        PromotionPolicy(
            require_human_approval=False,
            minimum_target_gain=-1.0,
            maximum_overall_regression=0.02,
        )
    )
    baseline = _report(0.80, [_score("policy-001", 0.80, True), _score("policy-002", 0.80, True)])
    candidate = _report(0.75, [_score("policy-001", 0.75, True), _score("policy-002", 0.75, True)])

    result = gate.evaluate(baseline, candidate)

    assert result.passed is False
    assert any(
        check.name == "maximum_overall_regression" and not check.passed
        for check in result.checks
    )


def test_promotion_gate_fails_candidate_with_critical_task_regression() -> None:
    gate = PromotionGate(
        PromotionPolicy(require_human_approval=False, minimum_target_gain=-1.0)
    )
    baseline = _report(
        0.85,
        [_score("critical-policy-001", 0.90, True), _score("policy-002", 0.80, True)],
    )
    candidate = _report(
        0.82,
        [_score("critical-policy-001", 0.40, False), _score("policy-002", 0.95, True)],
    )

    result = gate.evaluate(baseline, candidate)

    assert result.passed is False
    assert any(
        check.name == "critical_task_regressions" and not check.passed
        for check in result.checks
    )
