"""FastAPI dependency providers for API route handlers."""

from __future__ import annotations

from harness_foundry.catalog.repository import CatalogRepository
from harness_foundry.catalog.service import CatalogService


async def get_catalog_service() -> CatalogService:
    """Return an initialized catalog service."""

    repo = CatalogRepository()
    await repo.init()
    return CatalogService(repo)
