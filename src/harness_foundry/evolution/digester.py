"""Failure trace digestion for the constrained evolution pipeline."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from harness_foundry.schema import HarnessDefinition, TaskScore, TraceEvent


class TraceDigester:
    """Analyzes failed traces and identifies recurring failure patterns."""

    async def digest(
        self,
        failed_traces: list[TraceEvent],
        task_scores: list[TaskScore],
        successful_traces: list[TraceEvent],
        current_harness: HarnessDefinition,
        prior_history: list[dict],
    ) -> dict[str, Any]:
        """Return structured failure analysis.

        Args:
            failed_traces: All trace events associated with failed tasks.
            task_scores: Deterministic task scores for the evaluation run.
            successful_traces: Trace events associated with successful tasks.
            current_harness: Current harness under analysis.
            prior_history: Prior evolution decisions or summaries.

        Returns:
            A structured failure analysis with evidence-backed clusters.
        """

        del successful_traces, current_harness, prior_history

        failed_scores = [score for score in task_scores if not score.passed]
        family_by_task = self._family_by_task(failed_traces)
        traces_by_task = self._group_by_task(failed_traces)

        cluster_rows: list[dict[str, Any]] = []
        recurring_rows: list[dict[str, Any]] = []
        all_trace_ids: list[str] = []
        pattern_counter: Counter[str] = Counter()
        evidence_map: defaultdict[str, list[str]] = defaultdict(list)

        for score in failed_scores:
            pattern = self._pattern_for_score(score)
            task_traces = traces_by_task.get(score.task_id, [])
            trace_ids = sorted({event.trace_id for event in task_traces})
            family = family_by_task.get(score.task_id, "unknown")
            cluster_rows.append(
                {
                    "pattern": pattern,
                    "task_ids": [score.task_id],
                    "count": len(trace_ids) or 1,
                    "family": family,
                }
            )
            pattern_counter[pattern] += 1
            evidence_map[pattern].extend(trace_ids)
            all_trace_ids.extend(trace_ids)

        for pattern, count in pattern_counter.items():
            recurring_rows.append(
                {
                    "pattern": pattern,
                    "frequency": round(count / len(failed_scores), 4) if failed_scores else 0.0,
                    "evidence": sorted(set(evidence_map[pattern])),
                }
            )

        interpretation = await self._interpret_patterns_with_meta_agent(
            cluster_rows=cluster_rows,
            recurring_rows=recurring_rows,
        )

        return {
            "failure_clusters": cluster_rows,
            "recurring_patterns": recurring_rows,
            "supporting_trace_ids": sorted(set(all_trace_ids)),
            "possible_harness_causes": interpretation["possible_harness_causes"],
            "uncertainties": interpretation["uncertainties"],
        }

    def _pattern_for_score(self, score: TaskScore) -> str:
        if score.failure_codes:
            return ", ".join(sorted(score.failure_codes))
        return "unknown_failure"

    def _group_by_task(self, traces: list[TraceEvent]) -> dict[str, list[TraceEvent]]:
        grouped: defaultdict[str, list[TraceEvent]] = defaultdict(list)
        for event in traces:
            grouped[event.task_id].append(event)
        return dict(grouped)

    def _family_by_task(self, traces: list[TraceEvent]) -> dict[str, str]:
        families: dict[str, str] = {}
        for event in traces:
            family = event.metadata.get("family")
            if isinstance(family, str) and family:
                families.setdefault(event.task_id, family)
        return families

    async def _interpret_patterns_with_meta_agent(
        self,
        *,
        cluster_rows: list[dict[str, Any]],
        recurring_rows: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        """Return a deterministic placeholder for future meta-agent analysis."""

        causes: list[str] = []
        if any("grounding" in row["pattern"] for row in recurring_rows):
            causes.append("Grounding failures suggest missing evidence-enforcement behavior.")
        if any("tool_use" in row["pattern"] for row in recurring_rows):
            causes.append("Tool-use failures suggest processor or instruction misalignment.")
        if any("efficiency" in row["pattern"] for row in recurring_rows):
            causes.append("Efficiency failures suggest the harness may be allowing excess steps.")
        if not causes and cluster_rows:
            causes.append("Observed failures suggest a bounded configuration adjustment is needed.")

        uncertainties = (
            []
            if not cluster_rows
            else ["Interpretation is placeholder-only until meta-agent integration lands."]
        )

        return {
            "possible_harness_causes": causes,
            "uncertainties": uncertainties,
        }
