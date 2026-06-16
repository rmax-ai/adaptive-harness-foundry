"""Compilation of harness definitions into ADK agents."""

from __future__ import annotations

from typing import Any, cast

import structlog
from google.adk.agents.llm_agent import LlmAgent

from harness_foundry.runtime.callbacks import (
    CallbackFactory,
    ProcessorRegistry,
    get_processor_registry,
)
from harness_foundry.schema import HarnessDefinition, LifecycleHook, ProcessorInstance
from harness_foundry.tools.registry import ToolCallable, get_all_tools

logger = structlog.get_logger()


class HarnessCompiler:
    """Compile immutable harness definitions into ADK ``LlmAgent`` instances."""

    def __init__(self, processor_registry: ProcessorRegistry | None = None):
        self.registry = processor_registry or get_processor_registry()
        self.callback_factory = CallbackFactory(self.registry)

    def compile(self, harness: HarnessDefinition) -> LlmAgent:
        """Compile a harness definition into an ADK ``LlmAgent`` with callbacks."""

        tools = self._select_tools(harness)
        instruction = harness.agent.instruction
        if harness.agent.instruction_append:
            instruction = f"{instruction}\n\n{harness.agent.instruction_append}"

        logger.info(
            "harness_compiled",
            harness_id=harness.id,
            version=harness.version,
            tool_count=len(tools),
            processor_hook_count=len(harness.processors),
        )

        return LlmAgent(
            name=harness.agent.name,
            model=harness.model.model,
            instruction=instruction,
            tools=cast(Any, tools),
            before_agent_callback=self.callback_factory.create_before_agent_callback(
                self._processors_for_hook(harness, LifecycleHook.TASK_START),
                harness,
            ),
            after_agent_callback=self.callback_factory.create_after_agent_callback(
                self._processors_for_hook(harness, LifecycleHook.TASK_END),
                harness,
            ),
            before_model_callback=self.callback_factory.create_before_model_callback(
                self._processors_for_hook(harness, LifecycleHook.BEFORE_MODEL),
                harness,
            ),
            after_model_callback=self.callback_factory.create_after_model_callback(
                self._processors_for_hook(harness, LifecycleHook.AFTER_MODEL),
                harness,
            ),
            before_tool_callback=self.callback_factory.create_before_tool_callback(
                self._processors_for_hook(harness, LifecycleHook.BEFORE_TOOL),
                harness,
            ),
            after_tool_callback=self.callback_factory.create_after_tool_callback(
                self._processors_for_hook(harness, LifecycleHook.AFTER_TOOL),
                harness,
            ),
        )

    def _select_tools(self, harness: HarnessDefinition) -> list[ToolCallable]:
        """Filter registered tools according to harness policy."""

        tools = get_all_tools()
        if not harness.tools.allow:
            return tools

        allowlist = set(harness.tools.allow)
        return [tool for tool in tools if getattr(tool, "__name__", "") in allowlist]

    def _processors_for_hook(
        self,
        harness: HarnessDefinition,
        hook: LifecycleHook,
    ) -> list[ProcessorInstance]:
        if hook in harness.processors:
            return cast(list[ProcessorInstance], harness.processors[hook])

        for configured_hook, instances in harness.processors.items():
            if self._normalize_hook(configured_hook) == hook:
                return cast(list[ProcessorInstance], instances)
        return []

    def _normalize_hook(self, hook: LifecycleHook | str) -> LifecycleHook:
        if isinstance(hook, LifecycleHook):
            return hook

        candidate = hook.strip().upper()
        if candidate in LifecycleHook.__members__:
            return LifecycleHook[candidate]
        return LifecycleHook(hook)
