"""Compilation of harness definitions into ADK agents."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

import structlog
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from harness_foundry.schema import (
    HOOK_CAPABILITIES,
    HarnessDefinition,
    LifecycleHook,
    ProcessorContext,
    ProcessorEvent,
    ProcessorInstance,
    ProcessorResult,
)
from harness_foundry.tools.registry import ToolCallable, get_all_tools

logger = structlog.get_logger()

_LIFECYCLE_BUFFER_KEY = "harness_foundry:lifecycle_buffer"
_PROCESSOR_METADATA_KEY = "harness_foundry:processor_metadata"
_PROCESSOR_TERMINATED_KEY = "harness_foundry:processor_terminated"


class ProcessorRegistry(Protocol):
    """Protocol for resolving configured processors at runtime."""

    async def invoke(
        self,
        instance: ProcessorInstance,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        """Run a processor instance and return its normalized result."""


class HarnessCompiler:
    """Compile immutable harness definitions into ADK ``LlmAgent`` instances."""

    def __init__(self, processor_registry: ProcessorRegistry | None = None):
        self._processor_registry = processor_registry

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
            before_agent_callback=self._build_before_agent_callback(harness),
            after_agent_callback=self._build_after_agent_callback(harness),
            before_model_callback=self._build_before_model_callback(harness),
            after_model_callback=self._build_after_model_callback(harness),
            before_tool_callback=self._build_before_tool_callback(harness),
            after_tool_callback=self._build_after_tool_callback(harness),
        )

    def _select_tools(self, harness: HarnessDefinition) -> list[ToolCallable]:
        """Filter registered tools according to harness policy."""

        tools = get_all_tools()
        if not harness.tools.allow:
            return tools

        allowlist = set(harness.tools.allow)
        return [tool for tool in tools if getattr(tool, "__name__", "") in allowlist]

    def _build_before_agent_callback(
        self,
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[types.Content | None]]:
        async def callback(*, callback_context: Any) -> types.Content | None:
            await self._run_processor_chain(
                harness=harness,
                hook=LifecycleHook.TASK_START,
                state=callback_context.state,
                event_data={"run_id": callback_context.run_id},
            )
            return None

        return callback

    def _build_after_agent_callback(
        self,
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[types.Content | None]]:
        async def callback(*, callback_context: Any) -> types.Content | None:
            await self._run_processor_chain(
                harness=harness,
                hook=LifecycleHook.TASK_END,
                state=callback_context.state,
                event_data={"run_id": callback_context.run_id},
            )
            return None

        return callback

    def _build_before_model_callback(
        self,
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[LlmResponse | None]]:
        async def callback(
            *,
            callback_context: Any,
            llm_request: LlmRequest,
        ) -> LlmResponse | None:
            result = await self._run_processor_chain(
                harness=harness,
                hook=LifecycleHook.BEFORE_MODEL,
                state=callback_context.state,
                event_data={"model": llm_request.model},
            )
            if result.state_delta:
                self._merge_state(callback_context.state, result.state_delta)
            if result.block:
                return self._error_response("Model call blocked by harness processor.")
            if result.model_request_mod:
                updated_request = llm_request.model_copy(update=result.model_request_mod)
                llm_request.__dict__.update(updated_request.__dict__)
            return None

        return callback

    def _build_after_model_callback(
        self,
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[LlmResponse | None]]:
        async def callback(
            *,
            callback_context: Any,
            llm_response: LlmResponse,
        ) -> LlmResponse | None:
            result = await self._run_processor_chain(
                harness=harness,
                hook=LifecycleHook.AFTER_MODEL,
                state=callback_context.state,
                event_data={"model": self._response_model_name(llm_response)},
            )
            if result.state_delta:
                self._merge_state(callback_context.state, result.state_delta)
            if result.model_response_mod:
                return llm_response.model_copy(update=result.model_response_mod)
            return None

        return callback

    def _build_before_tool_callback(
        self,
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[dict[str, Any] | None]]:
        async def callback(
            *,
            tool: Any,
            args: dict[str, Any],
            tool_context: Any,
        ) -> dict[str, Any] | None:
            result = await self._run_processor_chain(
                harness=harness,
                hook=LifecycleHook.BEFORE_TOOL,
                state=tool_context.state,
                event_data={"tool_name": tool.name, "tool_arguments": args},
            )
            if result.state_delta:
                self._merge_state(tool_context.state, result.state_delta)
            if result.block:
                return {
                    "ok": False,
                    "error": "Tool call blocked by harness processor.",
                    "tool_name": tool.name,
                }
            if result.tool_args_mod:
                args.clear()
                args.update(result.tool_args_mod)
            return None

        return callback

    def _build_after_tool_callback(
        self,
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[dict[str, Any] | None]]:
        async def callback(
            *,
            tool: Any,
            args: dict[str, Any],
            tool_context: Any,
            tool_response: dict[str, Any],
        ) -> dict[str, Any] | None:
            result = await self._run_processor_chain(
                harness=harness,
                hook=LifecycleHook.AFTER_TOOL,
                state=tool_context.state,
                event_data={
                    "tool_name": tool.name,
                    "tool_arguments": args,
                    "tool_result": tool_response,
                },
            )
            if result.state_delta:
                self._merge_state(tool_context.state, result.state_delta)
            if isinstance(result.tool_result_mod, dict):
                return result.tool_result_mod
            return None

        return callback

    async def _run_processor_chain(
        self,
        *,
        harness: HarnessDefinition,
        hook: LifecycleHook,
        state: Any,
        event_data: dict[str, Any],
    ) -> ProcessorResult:
        instances = self._processors_for_hook(harness, hook)
        self._append_lifecycle_record(state, {"hook": hook.value, **event_data})
        if not instances or self._processor_registry is None:
            return ProcessorResult(
                allowed_capabilities={capability.value for capability in HOOK_CAPABILITIES[hook]},
            )

        aggregate = ProcessorResult(
            allowed_capabilities={capability.value for capability in HOOK_CAPABILITIES[hook]},
            state_delta={},
            metadata={},
        )
        processor_context = ProcessorContext(
            hook=hook,
            agent_name=harness.agent.name,
            task_id=str(state.get("harness:task_id", "")),
            harness_id=harness.id,
            state=dict(state),
        )
        processor_event = ProcessorEvent(hook=hook, data=event_data)

        for instance in instances:
            result = await self._invoke_processor(instance, processor_context, processor_event)
            aggregate = self._merge_processor_results(aggregate, result)
            if result.metadata:
                self._append_processor_metadata(state, hook, instance.type, result.metadata)
            if result.terminate:
                state[_PROCESSOR_TERMINATED_KEY] = True
                break
            if result.block:
                break

        return aggregate

    async def _invoke_processor(
        self,
        instance: ProcessorInstance,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        if self._processor_registry is None:
            return ProcessorResult(allowed_capabilities=set())

        invoke = getattr(self._processor_registry, "invoke", None)
        if invoke is None:
            raise TypeError("Processor registry must define an 'invoke' method.")

        result = invoke(instance=instance, context=context, event=event)
        if inspect.isawaitable(result):
            resolved = await result
        else:
            resolved = result
        return cast(ProcessorResult, resolved)

    def _processors_for_hook(
        self,
        harness: HarnessDefinition,
        hook: LifecycleHook,
    ) -> list[ProcessorInstance]:
        if hook in harness.processors:
            return harness.processors[hook]

        for configured_hook, instances in harness.processors.items():
            if self._normalize_hook(configured_hook) == hook:
                return instances
        return []

    def _normalize_hook(self, hook: LifecycleHook | str) -> LifecycleHook:
        if isinstance(hook, LifecycleHook):
            return hook

        candidate = hook.strip().upper()
        if candidate in LifecycleHook.__members__:
            return LifecycleHook[candidate]
        return LifecycleHook(hook)

    def _merge_processor_results(
        self,
        aggregate: ProcessorResult,
        result: ProcessorResult,
    ) -> ProcessorResult:
        state_delta = {**(aggregate.state_delta or {}), **(result.state_delta or {})}
        metadata = {**(aggregate.metadata or {}), **(result.metadata or {})}
        model_request_mod = {
            **(aggregate.model_request_mod or {}),
            **(result.model_request_mod or {}),
        }
        model_response_mod = {
            **(aggregate.model_response_mod or {}),
            **(result.model_response_mod or {}),
        }
        tool_args_mod = {**(aggregate.tool_args_mod or {}), **(result.tool_args_mod or {})}
        tool_result_mod = (
            result.tool_result_mod
            if result.tool_result_mod is not None
            else aggregate.tool_result_mod
        )

        return ProcessorResult(
            allowed_capabilities=aggregate.allowed_capabilities | result.allowed_capabilities,
            state_delta=state_delta or None,
            metadata=metadata or None,
            model_request_mod=model_request_mod or None,
            model_response_mod=model_response_mod or None,
            tool_args_mod=tool_args_mod or None,
            tool_result_mod=tool_result_mod,
            block=aggregate.block or result.block,
            terminate=aggregate.terminate or result.terminate,
            validation_failure=result.validation_failure or aggregate.validation_failure,
        )

    def _append_lifecycle_record(self, state: Any, record: dict[str, Any]) -> None:
        buffer = list(state.get(_LIFECYCLE_BUFFER_KEY, []))
        buffer.append(record)
        state[_LIFECYCLE_BUFFER_KEY] = buffer

    def _append_processor_metadata(
        self,
        state: Any,
        hook: LifecycleHook,
        processor_name: str,
        metadata: dict[str, Any],
    ) -> None:
        payload = list(state.get(_PROCESSOR_METADATA_KEY, []))
        payload.append(
            {
                "hook": hook.value,
                "processor_name": processor_name,
                "metadata": metadata,
            }
        )
        state[_PROCESSOR_METADATA_KEY] = payload

    def _merge_state(self, state: Any, state_delta: dict[str, Any]) -> None:
        for key, value in state_delta.items():
            state[key] = value

    def _error_response(self, message: str) -> LlmResponse:
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=message)]),
            error_message=message,
        )

    def _response_model_name(self, response: LlmResponse) -> str | None:
        return response.model_version
