"""Tool-focused processor implementations."""

from __future__ import annotations

from typing import Any, ClassVar

from harness_foundry.processors.base import (
    BaseProcessor,
    LifecycleHook,
    ProcessorCapability,
    ProcessorContext,
    ProcessorEvent,
    ProcessorResult,
)


class ToolAllowlistProcessor(BaseProcessor):
    """Block tool calls that are not permitted by the harness."""

    name = "tool_allowlist"
    version = "1.0.0"
    hook = LifecycleHook.BEFORE_TOOL
    description = "Blocks tool calls outside the configured harness allowlist."
    declared_reads: ClassVar[set[str]] = {"harness:allowed_tools"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {
        ProcessorCapability.BLOCK,
        ProcessorCapability.METADATA,
    }

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        allowed_tools: list[str] | None = None,
    ) -> None:
        super().__init__(config)
        self._allowed_tools = list(allowed_tools or self.config.get("allow", []))

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        tool_name = str(event.data.get("tool_name", "")).strip()
        allowed = self._allowed_tools or list(context.state.get("harness:allowed_tools", []))
        if not allowed or tool_name in allowed:
            return ProcessorResult()

        return ProcessorResult(
            block=True,
            validation_failure=f"Tool '{tool_name}' is not in the harness allowlist.",
            metadata={"tool_name": tool_name, "allowed_tools": allowed},
        )


class RequiredToolSequenceProcessor(BaseProcessor):
    """Record tool usage for later evaluation against required calls."""

    name = "required_tool_sequence"
    version = "1.0.0"
    hook = LifecycleHook.AFTER_TOOL
    description = "Records tool calls and tracks missing required tools."
    config_schema: ClassVar[dict[str, object]] = {
        "required_tools": {"type": "array"},
        "mode": {"type": "string"},
    }
    declared_reads: ClassVar[set[str]] = {"harness:tools:called"}
    declared_writes: ClassVar[set[ProcessorCapability]] = {
        ProcessorCapability.STATE,
        ProcessorCapability.METADATA,
    }

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        required_tools = list(self.config.get("required_tools", []))
        mode = str(self.config.get("mode", "record_only"))
        tool_name = str(event.data.get("tool_name", "")).strip()
        called = list(context.state.get("harness:tools:called", []))
        called.append(tool_name)
        missing = [tool for tool in required_tools if tool not in called]
        return ProcessorResult(
            state_delta={
                "harness:tools:called": called,
                "harness:tools:missing": missing,
            },
            metadata={"mode": mode, "missing_required_tools": missing},
        )


class MissingArgumentRepairProcessor(BaseProcessor):
    """Repair missing tool arguments when a safe default is configured."""

    name = "missing_argument_repair"
    version = "1.0.0"
    hook = LifecycleHook.BEFORE_TOOL
    description = "Fills in safe tool argument defaults for known missing parameters."
    config_schema: ClassVar[dict[str, object]] = {"defaults": {"type": "object"}}
    declared_reads: ClassVar[set[str]] = set()
    declared_writes: ClassVar[set[ProcessorCapability]] = {
        ProcessorCapability.TOOL_ARGUMENTS,
        ProcessorCapability.METADATA,
    }

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        tool_name = str(event.data.get("tool_name", "")).strip()
        tool_args = dict(event.data.get("tool_arguments", {}))
        defaults = self.config.get("defaults", {}).get(tool_name, {})
        repaired = False
        for key, value in defaults.items():
            if key not in tool_args:
                tool_args[key] = value
                repaired = True
        if not repaired:
            return ProcessorResult()

        return ProcessorResult(
            tool_args_mod=tool_args,
            metadata={"tool_name": tool_name, "repaired_keys": list(defaults)},
        )


class DryRunEnforcementProcessor(BaseProcessor):
    """Force dry-run mode for selected tools."""

    name = "dry_run_enforcement"
    version = "1.0.0"
    hook = LifecycleHook.BEFORE_TOOL
    description = "Injects dry_run=True for configured tools."
    config_schema: ClassVar[dict[str, object]] = {"dry_run_tools": {"type": "array"}}
    declared_reads: ClassVar[set[str]] = set()
    declared_writes: ClassVar[set[ProcessorCapability]] = {
        ProcessorCapability.TOOL_ARGUMENTS,
        ProcessorCapability.METADATA,
    }

    async def process(
        self,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        tool_name = str(event.data.get("tool_name", "")).strip()
        dry_run_tools = set(self.config.get("dry_run_tools", []))
        if tool_name not in dry_run_tools:
            return ProcessorResult()

        tool_args = dict(event.data.get("tool_arguments", {}))
        tool_args["dry_run"] = True
        return ProcessorResult(
            tool_args_mod=tool_args,
            metadata={"tool_name": tool_name, "dry_run_forced": True},
        )
