#!/usr/bin/env python3
"""Seed the catalog with the baseline harness and variants."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from harness_foundry.catalog.repository import CatalogRepository
from harness_foundry.catalog.service import CatalogService
from harness_foundry.schema.harness import HarnessLoader, VariantDefinition


async def main() -> None:
    """Create tables and register the baseline harness plus configured variants."""

    repo = CatalogRepository()
    await repo.init()
    service = CatalogService(repo)

    harness = HarnessLoader.load("configs/baseline.yaml")
    baseline_exists = await repo.get_harness(harness.id, harness.version)
    if baseline_exists is None:
        await service.register_harness(harness)
        print(f"Registered: {harness.id} v{harness.version}")
    else:
        print(f"Skipped existing: {harness.id} v{harness.version}")

    for name in ["policy_question", "account_lookup", "incident_triage"]:
        path = Path(f"configs/variants/{name}.yaml")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        variant = VariantDefinition.model_validate(data)
        resolved = variant.resolve(harness).model_copy(
            update={
                "id": data.get("id", harness.id),
                "version": data.get("version", harness.version),
                "author": data.get("author", harness.author),
                "status": data.get("status", harness.status),
                "parent_version": data.get("parent_version"),
            }
        )
        existing = await repo.get_harness(resolved.id, resolved.version)
        if existing is not None:
            print(
                f"Skipped existing variant: {resolved.id} v{resolved.version} "
                f"({resolved.task_family})"
            )
            continue
        try:
            await service.register_harness(resolved)
        except IntegrityError:
            print(
                f"Skipped duplicate variant: {resolved.id} v{resolved.version} "
                f"({resolved.task_family})"
            )
            continue
        print(f"Registered variant: {resolved.id} v{resolved.version} ({resolved.task_family})")


if __name__ == "__main__":
    asyncio.run(main())
