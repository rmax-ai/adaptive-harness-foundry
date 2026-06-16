"""FastAPI application factory for the operator UI and JSON endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    """Create and configure the API application."""

    app = FastAPI(title="Adaptive Harness Foundry", version="0.1.0")

    static_dir = Path(__file__).parent.parent / "ui" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    from harness_foundry.api.routes import router

    app.include_router(router)
    return app


app = create_app()
