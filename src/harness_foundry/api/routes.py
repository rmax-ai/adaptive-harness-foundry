"""Server-rendered UI routes and lightweight JSON API endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from harness_foundry.api.dependencies import get_catalog_service
from harness_foundry.catalog.models import HarnessVersionModel, PromotionRecordModel
from harness_foundry.catalog.service import CatalogService

router = APIRouter()
templates_dir = Path(__file__).parent.parent / "ui" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _serialize_harnesses(records: list[HarnessVersionModel]) -> list[dict[str, str | None]]:
    """Convert harness ORM records into template- and JSON-safe dicts."""

    return [
        {
            "id": record.id,
            "version": record.version,
            "status": record.status,
            "author": record.author,
            "task_family": record.task_family,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "parent_version": record.parent_version,
        }
        for record in records
    ]


def _serialize_promotions(records: list[PromotionRecordModel]) -> list[dict[str, str | int | None]]:
    """Convert promotion ORM records into JSON-safe dicts."""

    return [
        {
            "id": record.id,
            "baseline_id": record.baseline_id,
            "baseline_version": record.baseline_version,
            "candidate_id": record.candidate_id,
            "candidate_version": record.candidate_version,
            "decision": record.decision,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
        for record in records
    ]


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> HTMLResponse:
    """Main dashboard showing harness versions, benchmark results, and promotions."""

    harnesses = _serialize_harnesses(await catalog_service.repo.list_harnesses())
    active_harness = next((item for item in harnesses if item["status"] == "active"), None)
    pending_candidates = sum(1 for item in harnesses if item["status"] == "candidate")

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "title": "Adaptive Harness Foundry",
            "active_harness": active_harness,
            "last_benchmark_score": "N/A",
            "pending_candidates": pending_candidates,
        },
    )


@router.get("/harnesses", response_class=HTMLResponse)
async def harness_list(
    request: Request,
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> HTMLResponse:
    """List all harness versions."""

    harnesses = _serialize_harnesses(await catalog_service.repo.list_harnesses())
    return templates.TemplateResponse(
        request,
        "harnesses.html",
        {
            "request": request,
            "title": "Harnesses",
            "harnesses": harnesses,
        },
    )


@router.get("/api/harnesses")
async def api_harnesses(
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> JSONResponse:
    """API: list harnesses."""

    harnesses = _serialize_harnesses(await catalog_service.repo.list_harnesses())
    return JSONResponse({"harnesses": harnesses})


@router.get("/api/benchmarks")
async def api_benchmarks() -> JSONResponse:
    """API: list benchmark runs."""

    return JSONResponse({"runs": []})


@router.get("/api/promotions")
async def api_promotions(
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> JSONResponse:
    """API: list promotion records."""

    harnesses = await catalog_service.repo.list_harnesses()
    promotion_records: list[PromotionRecordModel] = []
    seen_ids: set[int] = set()
    for harness in harnesses:
        for record in await catalog_service.repo.list_promotions(harness.id):
            if record.id not in seen_ids:
                seen_ids.add(record.id)
                promotion_records.append(record)

    return JSONResponse({"promotions": _serialize_promotions(promotion_records)})
