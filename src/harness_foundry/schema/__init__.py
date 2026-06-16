"""Public schema exports for Adaptive Harness Foundry."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AgentConfig": "harness_foundry.schema.harness",
    "BenchmarkSplit": "harness_foundry.schema.benchmark",
    "BenchmarkTask": "harness_foundry.schema.benchmark",
    "ErrorRecord": "harness_foundry.schema.trace",
    "HOOK_CAPABILITIES": "harness_foundry.schema.processor",
    "HarnessDefinition": "harness_foundry.schema.harness",
    "HarnessLoader": "harness_foundry.schema.harness",
    "HarnessPatch": "harness_foundry.schema.benchmark",
    "HarnessRef": "harness_foundry.schema.harness",
    "LifecycleHook": "harness_foundry.schema.processor",
    "ModelConfig": "harness_foundry.schema.harness",
    "ProcessorCapability": "harness_foundry.schema.processor",
    "ProcessorContext": "harness_foundry.schema.processor",
    "ProcessorEvent": "harness_foundry.schema.processor",
    "ProcessorInstance": "harness_foundry.schema.harness",
    "ProcessorResult": "harness_foundry.schema.processor",
    "ProcessorSpec": "harness_foundry.schema.processor",
    "TaskScore": "harness_foundry.schema.benchmark",
    "TokenUsage": "harness_foundry.schema.trace",
    "ToolPolicy": "harness_foundry.schema.harness",
    "TraceEvent": "harness_foundry.schema.trace",
    "TraceRun": "harness_foundry.schema.trace",
    "VariantDefinition": "harness_foundry.schema.harness",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load schema exports lazily to avoid package-level circular imports."""

    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
