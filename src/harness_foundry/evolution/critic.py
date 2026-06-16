"""Patch review for constrained harness evolution."""

from __future__ import annotations

import json
import re
from typing import Any

from harness_foundry.schema import HarnessDefinition, HarnessPatch, ProcessorInstance, TaskScore


class CandidateCritic:
    """Reviews a proposed patch for safety, evidence, and reward hacking."""

    async def review(
        self,
        patch: HarnessPatch,
        current_harness: HarnessDefinition,
        pass_scores: list[TaskScore],
    ) -> dict[str, Any]:
        """Return structured review decision."""

        reasons: list[str] = []
        required_checks: list[str] = []
        risk_level = "low"

        if not patch.supporting_trace_ids:
            reasons.append("Patch lacks supporting trace IDs.")

        patch_text = json.dumps(patch.model_dump(mode="json"), sort_keys=True).lower()

        if self._looks_like_reward_hacking(patch_text):
            reasons.append("Patch appears to optimize for benchmark-specific literals.")
            risk_level = "high"

        if patch.operation == "update_tool_policy":
            reasons.append("Patch expands tool permissions, which is outside the bounded surface.")
            risk_level = "high"

        if self._contains_unbounded_loop_instruction(patch):
            reasons.append("Patch appears to encourage unbounded retry or looping behavior.")
            risk_level = "high"

        if self._duplicate_processor(patch, current_harness):
            reasons.append("Patch adds or conflicts with an existing processor configuration.")
            risk_level = "medium" if risk_level == "low" else risk_level

        if not self._schema_compatible(patch, current_harness):
            reasons.append("Patch is not schema-compatible with the current harness.")
            risk_level = "high"

        if self._has_broad_regression_risk(pass_scores):
            required_checks.append("Validate candidate on passing task families for regressions.")
            risk_level = "medium" if risk_level == "low" else risk_level

        if patch.operation in {"add_processor", "replace_processor", "update_processor_config"}:
            required_checks.append("Check processor ordering and runtime compatibility.")
        if patch.operation == "update_agent_instruction":
            required_checks.append("Check instruction changes for latency and verbosity impact.")

        decision = "reject" if reasons else "approve_for_evaluation"
        return {
            "decision": decision,
            "reasons": reasons or ["Evidence and safety checks passed for bounded evaluation."],
            "required_checks": required_checks,
            "risk_level": risk_level,
        }

    def _looks_like_reward_hacking(self, patch_text: str) -> bool:
        patterns = [
            r"\bevo-[a-z0-9-]*\d+\b",
            r"\bexpected_answer\b",
            r"\bfixture_state\b",
            r"\bevaluator\b",
        ]
        return any(re.search(pattern, patch_text) for pattern in patterns)

    def _contains_unbounded_loop_instruction(self, patch: HarnessPatch) -> bool:
        if patch.operation != "update_agent_instruction":
            return False
        after = str(patch.after).lower()
        markers = ["retry until", "keep trying forever", "never stop", "loop until success"]
        return any(marker in after for marker in markers)

    def _duplicate_processor(
        self,
        patch: HarnessPatch,
        current_harness: HarnessDefinition,
    ) -> bool:
        if patch.operation != "add_processor":
            return False
        if not isinstance(patch.after, dict):
            return True
        processor = ProcessorInstance.model_validate(patch.after)
        configured = current_harness.processors.get(patch.target.upper(), [])
        return any(existing.type == processor.type for existing in configured)

    def _schema_compatible(
        self,
        patch: HarnessPatch,
        current_harness: HarnessDefinition,
    ) -> bool:
        if patch.operation == "add_processor":
            try:
                ProcessorInstance.model_validate(patch.after)
            except Exception:
                return False
            return patch.target.upper() in {hook.value for hook in current_harness.processors} | {
                "TASK_START",
                "STEP_START",
                "BEFORE_MODEL",
                "AFTER_MODEL",
                "BEFORE_TOOL",
                "AFTER_TOOL",
                "STEP_END",
                "TASK_END",
            }
        return True

    def _has_broad_regression_risk(self, pass_scores: list[TaskScore]) -> bool:
        if not pass_scores:
            return False
        passing_families = {score.task_id.split("-", 1)[0] for score in pass_scores}
        return len(passing_families) > 1
