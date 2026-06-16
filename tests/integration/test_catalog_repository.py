"""Integration tests for catalog persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_foundry.catalog import CatalogRepository, PromotionRecordModel
from harness_foundry.schema import AgentConfig, HarnessDefinition, ModelConfig, ToolPolicy


def _build_harness(*, version: str = "1.0.0", status: str = "active") -> HarnessDefinition:
    return HarnessDefinition(
        id="support-harness",
        version=version,
        parent_version=None if version == "1.0.0" else "1.0.0",
        author="human",
        task_family="default",
        status=status,
        model=ModelConfig(provider="google", model="gemini-2.0-flash"),
        agent=AgentConfig(
            name="support_agent",
            instruction="Help the user.",
            instruction_append=None,
            maximum_steps=4,
        ),
        tools=ToolPolicy(allow=["get_customer"]),
        processors={},
    )


@pytest.mark.asyncio
async def test_catalog_repository_persists_and_reads_harnesses(tmp_path: Path) -> None:
    repository = CatalogRepository(db_url=f"sqlite:///{tmp_path / 'catalog.db'}")
    await repository.init()

    harness = _build_harness()
    await repository.save_harness(harness)

    loaded = await repository.get_harness("support-harness", "1.0.0")
    active = await repository.get_active_harness("support-harness")
    all_harnesses = await repository.list_harnesses("support-harness")

    assert loaded == harness
    assert active == harness
    assert len(all_harnesses) == 1
    assert all_harnesses[0].config_hash == harness.config_hash()


@pytest.mark.asyncio
async def test_catalog_repository_persists_promotion_records(tmp_path: Path) -> None:
    repository = CatalogRepository(db_url=f"sqlite:///{tmp_path / 'catalog.db'}")
    await repository.init()

    harness = _build_harness()
    candidate = _build_harness(version="1.0.1", status="candidate")
    await repository.save_harness(harness)
    await repository.save_harness(candidate)
    await repository.save_promotion(
        PromotionRecordModel(
            baseline_id=harness.id,
            baseline_version=harness.version,
            candidate_id=candidate.id,
            candidate_version=candidate.version,
            baseline_hash=harness.config_hash(),
            candidate_hash=candidate.config_hash(),
            patch_json={"operation": "update_tool_policy"},
            gate_results={"score": 1.0},
            decision="accepted",
        )
    )

    promotions = await repository.list_promotions(harness.id)

    assert len(promotions) == 1
    assert promotions[0].candidate_version == "1.0.1"
    assert promotions[0].decision == "accepted"
