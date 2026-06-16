"""End-to-end constrained evolution pipeline orchestration."""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from harness_foundry.catalog import CatalogService
from harness_foundry.catalog.service import GateResult as CatalogGateResult
from harness_foundry.evaluation import BenchmarkReport, BenchmarkRunner
from harness_foundry.evolution.critic import CandidateCritic
from harness_foundry.evolution.digester import TraceDigester
from harness_foundry.evolution.evolver import CandidateEvolver
from harness_foundry.evolution.linter import PatchLinter
from harness_foundry.evolution.planner import FailurePlanner
from harness_foundry.evolution.promotion import GateResult, PromotionGate
from harness_foundry.schema import HarnessDefinition, HarnessPatch, TraceEvent

logger = structlog.get_logger()


class EvolutionResult(BaseModel):
    """Structured result from one evolution cycle."""

    model_config = ConfigDict(frozen=True)

    baseline_run_id: str = Field(..., min_length=1)
    candidate_version: str | None = None
    status: str = Field(..., min_length=1)
    digestion: dict[str, Any] = Field(default_factory=dict)
    plan: dict[str, Any] = Field(default_factory=dict)
    patch: HarnessPatch | None = None
    lint_violations: list[str] = Field(default_factory=list)
    critic_review: dict[str, Any] = Field(default_factory=dict)
    baseline_report: BenchmarkReport | None = None
    candidate_report: BenchmarkReport | None = None
    gate_result: GateResult | None = None


class EvolutionPipeline:
    """Orchestrates the full evolution cycle."""

    EVOLUTION_SPLIT = "evolution"

    def __init__(
        self,
        digester: TraceDigester,
        planner: FailurePlanner,
        evolver: CandidateEvolver,
        critic: CandidateCritic,
        linter: PatchLinter,
        catalog: CatalogService,
        benchmark_runner: BenchmarkRunner,
        promotion_gate: PromotionGate,
    ):
        self._digester = digester
        self._planner = planner
        self._evolver = evolver
        self._critic = critic
        self._linter = linter
        self._catalog = catalog
        self._benchmark_runner = benchmark_runner
        self._promotion_gate = promotion_gate

    async def run(
        self,
        harness: HarnessDefinition,
        baseline_run_id: str,
    ) -> EvolutionResult:
        """Run one complete evolution cycle."""

        try:
            baseline_report = await self._benchmark_runner.run_benchmark(
                harness=harness,
                split=self.EVOLUTION_SPLIT,
            )
            baseline_events = await self._load_run_events(baseline_run_id)
            failed_scores = [score for score in baseline_report.scores if not score.passed]
            passed_scores = [score for score in baseline_report.scores if score.passed]

            failed_task_ids = {score.task_id for score in failed_scores}
            failed_traces = [event for event in baseline_events if event.task_id in failed_task_ids]
            successful_traces = [
                event for event in baseline_events if event.task_id not in failed_task_ids
            ]

            digestion = await self._digester.digest(
                failed_traces=failed_traces,
                task_scores=baseline_report.scores,
                successful_traces=successful_traces,
                current_harness=harness,
                prior_history=[],
            )
            if not failed_scores:
                return EvolutionResult(
                    baseline_run_id=baseline_run_id,
                    status="no_action",
                    digestion=digestion,
                    baseline_report=baseline_report,
                    critic_review={
                        "decision": "reject",
                        "reasons": ["No failed tasks were available for adaptation."],
                        "required_checks": [],
                        "risk_level": "low",
                    },
                )

            plan = await self._planner.plan(digestion=digestion, current_harness=harness)
            patch = await self._evolver.evolve(
                plan=plan,
                current_harness=harness,
                failure_traces=failed_traces,
            )

            lint_violations = self._linter.lint(patch=patch, current_harness=harness)
            critic_review = await self._critic.review(
                patch=patch,
                current_harness=harness,
                pass_scores=passed_scores,
            )

            if lint_violations or critic_review["decision"] != "approve_for_evaluation":
                return EvolutionResult(
                    baseline_run_id=baseline_run_id,
                    status="rejected_pre_evaluation",
                    digestion=digestion,
                    plan=plan,
                    patch=patch,
                    lint_violations=lint_violations,
                    critic_review=critic_review,
                    baseline_report=baseline_report,
                )

            candidate = await self._catalog.create_candidate(
                base_harness=harness,
                patch=patch,
                author="meta_agent",
            )
            candidate_report = await self._benchmark_runner.run_benchmark(
                harness=candidate,
                split=baseline_report.split,
            )
            gate_result = self._promotion_gate.evaluate(
                baseline=baseline_report,
                candidate=candidate_report,
                simulate_approval=False,
            )
            await self._catalog.promote_candidate(
                candidate.id,
                candidate.version,
                CatalogGateResult(
                    decision="accepted" if gate_result.passed else "rejected",
                    summary=gate_result.model_dump(mode="python"),
                    patch=patch.model_dump(mode="python"),
                ),
            )

            return EvolutionResult(
                baseline_run_id=baseline_run_id,
                candidate_version=candidate.version,
                status="promoted" if gate_result.passed else "evaluated_rejected",
                digestion=digestion,
                plan=plan,
                patch=patch,
                lint_violations=lint_violations,
                critic_review=critic_review,
                baseline_report=baseline_report,
                candidate_report=candidate_report,
                gate_result=gate_result,
            )
        except Exception:
            logger.exception(
                "evolution_pipeline_failed",
                harness_id=harness.id,
                baseline_run_id=baseline_run_id,
            )
            raise

    async def _load_run_events(self, baseline_run_id: str) -> list[TraceEvent]:
        tracer = getattr(self._benchmark_runner, "_tracer", None)
        if tracer is None:
            return []
        return await tracer.get_run_events(baseline_run_id)
