"""Static lint rules for evolution patches."""

from __future__ import annotations

import json
import re

from harness_foundry.schema import HarnessDefinition, HarnessPatch


class PatchLinter:
    """Static analysis rejecting patches that compromise safety."""

    TASK_ID_PATTERN = re.compile(r"\bevo-[a-z0-9-]*\d+\b", re.IGNORECASE)
    ANSWER_FRAGMENT_PATTERN = re.compile(
        r"\b(expected answer|golden answer|correct response)\b",
        re.IGNORECASE,
    )
    CUSTOMER_LITERAL_PATTERN = re.compile(
        r"\b(customer_id|account_number|balance_due|refund_amount)\b",
        re.IGNORECASE,
    )
    EVALUATOR_PATTERN = re.compile(r"\bevaluator[s]?\b", re.IGNORECASE)
    FIXTURE_PATTERN = re.compile(r"\bfixtures?/|data/benchmarks/|\.yaml\b", re.IGNORECASE)

    def lint(self, patch: HarnessPatch, current_harness: HarnessDefinition) -> list[str]:
        """Return list of violation descriptions (empty = clean)."""

        violations: list[str] = []
        patch_text = json.dumps(patch.model_dump(mode="json"), sort_keys=True)

        if self.TASK_ID_PATTERN.search(patch_text):
            violations.append("Patch references benchmark task IDs.")
        if self.ANSWER_FRAGMENT_PATTERN.search(patch_text):
            violations.append("Patch contains expected-answer fragments.")
        if self.CUSTOMER_LITERAL_PATTERN.search(patch_text):
            violations.append("Patch contains suspicious literal customer-result fields.")
        if self.EVALUATOR_PATTERN.search(patch_text):
            violations.append("Patch references evaluator internals.")
        if self.FIXTURE_PATTERN.search(patch_text):
            violations.append("Patch references benchmark fixtures or dataset paths.")
        if self._touches_promotion_config(patch):
            violations.append("Patch attempts to modify promotion policy or gate settings.")
        if self._disables_tracing(patch):
            violations.append("Patch attempts to disable tracing or observability.")
        if self._expands_tool_permissions(patch, current_harness):
            violations.append("Patch expands the tool allowlist.")

        return violations

    def _touches_promotion_config(self, patch: HarnessPatch) -> bool:
        serialized = f"{patch.target} {patch.rationale}".lower()
        return "promotion" in serialized or "gate" in serialized

    def _disables_tracing(self, patch: HarnessPatch) -> bool:
        serialized = json.dumps(patch.model_dump(mode="json"), sort_keys=True).lower()
        tracing_markers = [
            "disable_tracing",
            'tracing_enabled": false',
            'observability_enabled": false',
            "turn off tracing",
        ]
        return any(marker in serialized for marker in tracing_markers)

    def _expands_tool_permissions(
        self,
        patch: HarnessPatch,
        current_harness: HarnessDefinition,
    ) -> bool:
        if patch.operation != "update_tool_policy":
            return False
        if not isinstance(patch.after, list):
            return True
        current = set(current_harness.tools.allow)
        proposed = {str(tool_name) for tool_name in patch.after}
        return not proposed.issubset(current)
