"""Unit tests for catalog service workflows."""

from __future__ import annotations

import pytest

from harness_foundry.catalog import CatalogRepository, CatalogService, GateResult
from harness_foundry.schema import (
    AgentConfig,
    HarnessDefinition,
    HarnessPatch,
    ModelConfig,
    ProcessorInstance,
    ToolPolicy,
)


def _build_harness() -> HarnessDefinition:
    return HarnessDefinition(
        id="support-harness",
        version="1.0.0",
        parent_version=None,
        author="human",
        task_family="default",
        status="active",
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
async def test_catalog_service_creates_candidate_with_bumped_version(tmp_path) -> None:
    repository = CatalogRepository(db_url=f"sqlite:///{tmp_path / 'catalog.db'}")
    await repository.init()

    service = CatalogService(repository)
    base = _build_harness()
    await service.register_harness(base)

    patch = HarnessPatch(
        operation="add_processor",
        target="before_model",
        after=ProcessorInstance(type="safety", version="1.0.0", config={"strict": True}),
        rationale="Add pre-model safety screening.",
        predicted_benefit="Better blocking.",
    )

    candidate = await service.create_candidate(base, patch, author="meta_agent")

    assert candidate.version == "1.0.1"
    assert candidate.parent_version == "1.0.0"
    assert candidate.status == "candidate"
    assert candidate.author == "meta_agent"
    assert candidate.processors["BEFORE_MODEL"][0].type == "safety"


@pytest.mark.asyncio
async def test_catalog_service_promotes_candidate_to_active(tmp_path) -> None:
    repository = CatalogRepository(db_url=f"sqlite:///{tmp_path / 'catalog.db'}")
    await repository.init()

    service = CatalogService(repository)
    base = _build_harness()
    await service.register_harness(base)

    candidate = await service.create_candidate(
        base,
        HarnessPatch(
            operation="update_tool_policy",
            target="tools.allow",
            after=["get_customer", "search_policy"],
            rationale="Allow policy lookups.",
            predicted_benefit="More grounded responses.",
        ),
        author="meta_agent",
    )
    await service.promote_candidate(
        candidate.id,
        candidate.version,
        GateResult(
            decision="accepted",
            summary={"score": 0.95},
            patch={"operation": "update_tool_policy"},
        ),
    )

    active = await service.get_active(base.id)
    archived_base = await repository.get_harness(base.id, base.version)

    assert active.version == candidate.version
    assert active.status == "active"
    assert archived_base is not None
    assert archived_base.status == "archived"
