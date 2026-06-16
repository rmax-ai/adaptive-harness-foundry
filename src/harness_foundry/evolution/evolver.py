"""Structured patch generation for constrained harness evolution."""

from __future__ import annotations

from typing import Any

from harness_foundry.schema import HarnessDefinition, HarnessPatch, ProcessorInstance, TraceEvent


class CandidateEvolver:
    """Generates exactly one structured HarnessPatch from a plan."""

    async def evolve(
        self,
        plan: dict[str, Any],
        current_harness: HarnessDefinition,
        failure_traces: list[TraceEvent],
    ) -> HarnessPatch:
        """Generate a bounded configuration patch."""

        trace_ids = self._trace_ids_for_family(
            traces=failure_traces,
            target_family=str(plan.get("target_task_family", "default")),
        )
        if not trace_ids:
            trace_ids = [
                trace_id
                for trace_id in plan.get("supporting_trace_ids", [])
                if isinstance(trace_id, str) and trace_id
            ]

        patch_payload = await self._generate_patch_with_meta_agent(
            plan=plan,
            current_harness=current_harness,
            trace_ids=trace_ids,
        )
        return HarnessPatch.model_validate(patch_payload)

    def _trace_ids_for_family(
        self,
        *,
        traces: list[TraceEvent],
        target_family: str,
    ) -> list[str]:
        trace_ids: list[str] = []
        for event in traces:
            family = event.metadata.get("family")
            if family == target_family:
                trace_ids.append(event.trace_id)
        return sorted(set(trace_ids))

    async def _generate_patch_with_meta_agent(
        self,
        *,
        plan: dict[str, Any],
        current_harness: HarnessDefinition,
        trace_ids: list[str],
    ) -> dict[str, Any]:
        """Return a deterministic placeholder patch pending LLM integration."""

        objective = str(plan.get("objective", "update_agent_instruction"))
        target_hook = str(plan.get("target_hook", "BEFORE_MODEL")).upper()
        target_family = str(plan.get("target_task_family", current_harness.task_family))
        reasoning = str(plan.get("reasoning", "Bounded adaptation selected from failure review."))

        if objective == "add_processor":
            processor = ProcessorInstance(
                type="citation_requirement",
                version="1.0.0",
                config={"task_family": target_family, "mode": "strict"},
            )
            return {
                "operation": "add_processor",
                "target": target_hook,
                "before": None,
                "after": processor.model_dump(mode="python"),
                "rationale": reasoning,
                "supporting_trace_ids": trace_ids,
                "predicted_benefit": "Improves evidence enforcement before model generation.",
                "possible_regressions": ["May over-constrain some responses."],
            }

        if objective == "update_processor_config":
            processors = current_harness.processors.get(target_hook, [])
            if processors:
                processor = processors[0]
                config_delta = {"strict_mode": True}
                return {
                    "operation": "update_processor_config",
                    "target": f"{target_hook}:{processor.type}",
                    "before": dict(processor.config),
                    "after": config_delta,
                    "rationale": reasoning,
                    "supporting_trace_ids": trace_ids,
                    "predicted_benefit": "Tightens an existing processor without widening scope.",
                    "possible_regressions": ["May reduce flexibility for borderline tasks."],
                }

        if objective == "create_variant":
            return {
                "operation": "create_variant",
                "target": current_harness.task_family,
                "before": current_harness.task_family,
                "after": {"task_family": target_family},
                "rationale": reasoning,
                "supporting_trace_ids": trace_ids,
                "predicted_benefit": "Isolates adaptation to the failing task family.",
                "possible_regressions": ["Variant management complexity increases."],
            }

        before_value = current_harness.agent.instruction_append
        after_value = self._append_instruction(
            base=current_harness.agent.instruction_append,
            addition=(
                f"Prioritize grounded answers for {target_family} tasks and cite tool-backed "
                "evidence when available."
            ),
        )
        return {
            "operation": "update_agent_instruction",
            "target": "instruction_append",
            "before": before_value,
            "after": after_value,
            "rationale": reasoning,
            "supporting_trace_ids": trace_ids,
            "predicted_benefit": "Improves agent behavior without changing tool permissions.",
            "possible_regressions": ["Longer instructions may slightly increase latency."],
        }

    def _append_instruction(self, *, base: str | None, addition: str) -> str:
        if not base:
            return addition
        if addition in base:
            return base
        return f"{base.rstrip()} {addition}"
