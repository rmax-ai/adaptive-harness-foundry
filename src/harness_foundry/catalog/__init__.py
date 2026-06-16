"""Catalog exports for Adaptive Harness Foundry."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CatalogRepository": "harness_foundry.catalog.repository",
    "CatalogService": "harness_foundry.catalog.service",
    "GateResult": "harness_foundry.catalog.service",
    "HarnessVersionModel": "harness_foundry.catalog.models",
    "PromotionRecordModel": "harness_foundry.catalog.models",
    "canonical_json": "harness_foundry.catalog.hashing",
    "config_sha256": "harness_foundry.catalog.hashing",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load catalog exports lazily to avoid package-level circular imports."""

    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
