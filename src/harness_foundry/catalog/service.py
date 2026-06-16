"""Catalog service for harness registration, candidate creation, and promotion."""

from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from harness_foundry.catalog.models import PromotionRecordModel
from harness_foundry.catalog.repository import CatalogRepository
from harness_foundry.schema import HarnessDefinition, HarnessPatch, LifecycleHook, ProcessorInstance


class GateResult(BaseModel):
    """Promotion gate outcome used to record candidate decisions."""

    model_config = ConfigDict(frozen=True)

    decision: Literal["accepted", "rejected"]
    summary: dict[str, Any] = Field(default_factory=dict)
    patch: dict[str, Any] = Field(default_factory=dict)


class CatalogService:
    """Application service for higher-level catalog workflows."""

    def __init__(self, repo: CatalogRepository):
        self.repo = repo

    async def register_harness(self, harness: HarnessDefinition) -> str:
        """Register a new harness and return its configuration hash."""

        await self.repo.save_harness(harness)
        return cast(str, harness.config_hash())

    async def create_candidate(
        self,
        base_harness: HarnessDefinition,
        patch: HarnessPatch,
        author: str,
    ) -> HarnessDefinition:
        """Apply a patch to create a candidate harness with a bumped version."""

        candidate_payload = base_harness.model_dump(mode="python")
        candidate_payload["version"] = self._next_version(base_harness.version)
        candidate_payload["parent_version"] = base_harness.version
        candidate_payload["author"] = self._normalize_author(author)
        candidate_payload["status"] = "candidate"

        self._apply_patch(candidate_payload, patch)

        candidate = HarnessDefinition.model_validate(candidate_payload)
        await self.repo.save_harness(candidate)
        return candidate

    async def promote_candidate(
        self,
        candidate_id: str,
        candidate_version: str,
        gate_result: GateResult,
    ) -> None:
        """Record a promotion decision and update harness status."""

        candidate = await self.repo.get_harness(candidate_id, candidate_version)
        if candidate is None:
            raise LookupError(f"Candidate {candidate_id} v{candidate_version} was not found.")
        if candidate.parent_version is None:
            raise ValueError("Candidate harness is missing parent_version.")

        baseline = await self.repo.get_harness(candidate.id, candidate.parent_version)
        if baseline is None:
            raise LookupError(
                "Baseline "
                f"{candidate.id} v{candidate.parent_version} for candidate promotion "
                "was not found."
            )

        record = PromotionRecordModel(
            baseline_id=baseline.id,
            baseline_version=baseline.version,
            candidate_id=candidate.id,
            candidate_version=candidate.version,
            baseline_hash=baseline.config_hash(),
            candidate_hash=candidate.config_hash(),
            patch_json=gate_result.patch,
            gate_results=gate_result.summary,
            decision=gate_result.decision,
        )
        await self.repo.save_promotion(record)

        if gate_result.decision == "accepted":
            active = await self.repo.get_active_harness(candidate.id)
            if active is not None and active.version != candidate.version:
                await self.repo.update_harness(active.model_copy(update={"status": "archived"}))
            await self.repo.update_harness(candidate.model_copy(update={"status": "active"}))
            return

        await self.repo.update_harness(candidate.model_copy(update={"status": "rejected"}))

    async def get_active(self, harness_id: str) -> HarnessDefinition:
        """Return the active harness for an ID."""

        harness = await self.repo.get_active_harness(harness_id)
        if harness is None:
            raise LookupError(f"No active harness found for {harness_id}.")
        return harness

    def _apply_patch(self, payload: dict[str, Any], patch: HarnessPatch) -> None:
        if patch.operation == "update_agent_instruction":
            target = (
                patch.target
                if patch.target in {"instruction", "instruction_append"}
                else "instruction"
            )
            payload["agent"][target] = patch.after
            return

        if patch.operation == "update_tool_policy":
            payload["tools"]["allow"] = list(patch.after)
            return

        if patch.operation == "create_variant":
            after = patch.after
            if isinstance(after, dict):
                payload["task_family"] = str(after.get("task_family", payload["task_family"]))
            else:
                payload["task_family"] = str(after)
            return

        hook, processor_type = self._parse_processor_target(patch.target)
        processors = payload.setdefault("processors", {})
        hook_processors = processors.setdefault(hook.value, [])

        if patch.operation == "add_processor":
            hook_processors.append(self._processor_instance_payload(patch.after))
            return

        match_index = self._find_processor_index(
            hook_processors,
            processor_type
            or self._extract_processor_type(patch.before)
            or self._extract_processor_type(patch.after),
        )
        if match_index is None:
            raise ValueError(
                f"Processor target {patch.target} did not match any configured processor."
            )

        if patch.operation == "remove_processor":
            hook_processors.pop(match_index)
            return

        if patch.operation == "replace_processor":
            hook_processors[match_index] = self._processor_instance_payload(patch.after)
            return

        if patch.operation == "update_processor_config":
            updated = dict(hook_processors[match_index])
            existing_config = dict(updated.get("config", {}))
            existing_config.update(dict(patch.after))
            updated["config"] = existing_config
            hook_processors[match_index] = updated
            return

        raise ValueError(f"Unsupported patch operation: {patch.operation}")

    def _next_version(self, version: str) -> str:
        major, minor, patch = (int(part) for part in version.split("."))
        return f"{major}.{minor}.{patch + 1}"

    def _normalize_author(self, author: str) -> str:
        if author not in {"human", "meta_agent"}:
            raise ValueError(f"Unsupported author value: {author}")
        return author

    def _parse_processor_target(self, target: str) -> tuple[LifecycleHook, str | None]:
        if ":" in target:
            hook_name, processor_type = target.split(":", 1)
            return LifecycleHook[str(hook_name).strip().upper()], processor_type.strip() or None
        return LifecycleHook[target.strip().upper()], None

    def _processor_instance_payload(self, value: Any) -> dict[str, Any]:
        instance = ProcessorInstance.model_validate(value)
        return cast(dict[str, Any], instance.model_dump(mode="python"))

    def _extract_processor_type(self, value: Any) -> str | None:
        if isinstance(value, dict):
            instance_type = value.get("type")
            if isinstance(instance_type, str) and instance_type:
                return instance_type
        return None

    def _find_processor_index(
        self,
        processors: list[dict[str, Any]],
        processor_type: str | None,
    ) -> int | None:
        if processor_type is None:
            return 0 if processors else None

        for index, processor in enumerate(processors):
            if processor.get("type") == processor_type:
                return index
        return None
