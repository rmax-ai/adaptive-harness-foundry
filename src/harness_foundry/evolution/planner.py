"""Failure planning for constrained harness evolution."""

from __future__ import annotations

from typing import Any, ClassVar

from harness_foundry.schema import HarnessDefinition


class FailurePlanner:
    """Selects one bounded adaptation objective from failure analysis."""

    ALLOWED_OBJECTIVES: ClassVar[set[str]] = {
        "add_processor",
        "update_processor_config",
        "update_agent_instruction",
        "create_variant",
    }

    async def plan(
        self,
        digestion: dict[str, Any],
        current_harness: HarnessDefinition,
    ) -> dict[str, Any]:
        """Return exactly one adaptation objective."""

        del current_harness

        objective = await self._plan_with_meta_agent(digestion)
        normalized_objective = str(objective.get("objective", "update_agent_instruction"))
        if normalized_objective not in self.ALLOWED_OBJECTIVES:
            normalized_objective = "update_agent_instruction"

        supporting_trace_ids = [
            trace_id
            for trace_id in objective.get("supporting_trace_ids", [])
            if isinstance(trace_id, str) and trace_id
        ]
        if not supporting_trace_ids:
            supporting_trace_ids = list(digestion.get("supporting_trace_ids", []))[:2]

        return {
            "objective": normalized_objective,
            "target_hook": objective.get("target_hook", "BEFORE_MODEL"),
            "target_task_family": objective.get("target_task_family", "default"),
            "reasoning": objective.get(
                "reasoning",
                "Bounded adaptation selected from deterministic failure analysis.",
            ),
            "supporting_trace_ids": supporting_trace_ids,
        }

    async def _plan_with_meta_agent(self, digestion: dict[str, Any]) -> dict[str, Any]:
        """Return a deterministic placeholder plan pending LLM integration."""

        recurring = digestion.get("recurring_patterns", [])
        strongest_pattern = recurring[0]["pattern"] if recurring else "unknown_failure"
        failure_clusters = digestion.get("failure_clusters", [])
        target_family = failure_clusters[0]["family"] if failure_clusters else "default"

        if "grounding" in strongest_pattern or "tool_use" in strongest_pattern:
            objective = "add_processor"
            target_hook = "BEFORE_MODEL"
            reasoning = (
                "Failures suggest the harness needs a bounded pre-model processor "
                "to enforce evidence or tool-usage constraints."
            )
        elif "efficiency" in strongest_pattern:
            objective = "update_processor_config"
            target_hook = "STEP_END"
            reasoning = "Failures suggest an existing processor should tighten step limits."
        else:
            objective = "update_agent_instruction"
            target_hook = "TASK_END"
            reasoning = "Failures suggest the agent instruction needs a narrow behavioral update."

        return {
            "objective": objective,
            "target_hook": target_hook,
            "target_task_family": target_family,
            "reasoning": reasoning,
            "supporting_trace_ids": list(digestion.get("supporting_trace_ids", []))[:2],
        }
