"""Callback factory for wiring processor chains into ADK hooks."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

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

LIFECYCLE_BUFFER_KEY = "harness_foundry:lifecycle_buffer"
PROCESSOR_METADATA_KEY = "harness_foundry:processor_metadata"
PROCESSOR_TERMINATED_KEY = "harness_foundry:processor_terminated"


class ProcessorRegistry(Protocol):
    """Protocol for invoking configured processor instances."""

    async def invoke(
        self,
        instance: ProcessorInstance,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        """Run a processor instance and return its normalized result."""


class NoopProcessorRegistry:
    """Fallback registry used when no processor runtime is configured."""

    async def invoke(
        self,
        instance: ProcessorInstance,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        del instance, event
        return ProcessorResult(
            allowed_capabilities={
                capability.value for capability in HOOK_CAPABILITIES[context.hook]
            },
        )


def get_processor_registry() -> ProcessorRegistry:
    """Return the default runtime processor registry."""

    return NoopProcessorRegistry()


class CallbackFactory:
    """Creates ADK callback functions that invoke the processor chain."""

    def __init__(self, registry: ProcessorRegistry):
        self.registry = registry

    def create_before_agent_callback(
        self,
        processors: list[ProcessorInstance],
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[types.Content | None]]:
        """Create an async callback for TASK_START processors."""

        async def callback(*, callback_context: Any) -> types.Content | None:
            await self._run_processor_chain(
                processors=processors,
                harness=harness,
                hook=LifecycleHook.TASK_START,
                state=callback_context.state,
                event_data={"run_id": getattr(callback_context, "run_id", None)},
            )
            return None

        return callback

    def create_after_agent_callback(
        self,
        processors: list[ProcessorInstance],
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[types.Content | None]]:
        """Create an async callback for TASK_END processors."""

        async def callback(*, callback_context: Any) -> types.Content | None:
            await self._run_processor_chain(
                processors=processors,
                harness=harness,
                hook=LifecycleHook.TASK_END,
                state=callback_context.state,
                event_data={"run_id": getattr(callback_context, "run_id", None)},
            )
            return None

        return callback

    def create_before_model_callback(
        self,
        processors: list[ProcessorInstance],
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[LlmResponse | None]]:
        """Create an async callback for BEFORE_MODEL processors."""

        async def callback(*, callback_context: Any, llm_request: LlmRequest) -> LlmResponse | None:
            result = await self._run_processor_chain(
                processors=processors,
                harness=harness,
                hook=LifecycleHook.BEFORE_MODEL,
                state=callback_context.state,
                event_data={"model": llm_request.model},
            )
            if result.block:
                return self._error_response("Model call blocked by harness processor.")
            if result.model_request_mod:
                updated_request = llm_request.model_copy(update=result.model_request_mod)
                llm_request.__dict__.update(updated_request.__dict__)
            return None

        return callback

    def create_after_model_callback(
        self,
        processors: list[ProcessorInstance],
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[LlmResponse | None]]:
        """Create an async callback for AFTER_MODEL processors."""

        async def callback(
            *, callback_context: Any, llm_response: LlmResponse
        ) -> LlmResponse | None:
            result = await self._run_processor_chain(
                processors=processors,
                harness=harness,
                hook=LifecycleHook.AFTER_MODEL,
                state=callback_context.state,
                event_data={"model": self._response_model_name(llm_response)},
            )
            if result.model_response_mod:
                return llm_response.model_copy(update=result.model_response_mod)
            return None

        return callback

    def create_before_tool_callback(
        self,
        processors: list[ProcessorInstance],
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[dict[str, Any] | None]]:
        """Create an async callback for BEFORE_TOOL processors."""

        async def callback(
            *, tool: Any, args: dict[str, Any], tool_context: Any
        ) -> dict[str, Any] | None:
            tool_name = getattr(tool, "name", getattr(tool, "__name__", "tool"))
            result = await self._run_processor_chain(
                processors=processors,
                harness=harness,
                hook=LifecycleHook.BEFORE_TOOL,
                state=tool_context.state,
                event_data={"tool_name": tool_name, "tool_arguments": args},
            )
            if result.block:
                return {
                    "ok": False,
                    "error": "Tool call blocked by harness processor.",
                    "tool_name": tool_name,
                }
            if result.tool_args_mod:
                args.clear()
                args.update(result.tool_args_mod)
            return None

        return callback

    def create_after_tool_callback(
        self,
        processors: list[ProcessorInstance],
        harness: HarnessDefinition,
    ) -> Callable[..., Awaitable[dict[str, Any] | None]]:
        """Create an async callback for AFTER_TOOL processors."""

        async def callback(
            *,
            tool: Any,
            args: dict[str, Any],
            tool_context: Any,
            tool_response: dict[str, Any],
        ) -> dict[str, Any] | None:
            tool_name = getattr(tool, "name", getattr(tool, "__name__", "tool"))
            result = await self._run_processor_chain(
                processors=processors,
                harness=harness,
                hook=LifecycleHook.AFTER_TOOL,
                state=tool_context.state,
                event_data={
                    "tool_name": tool_name,
                    "tool_arguments": args,
                    "tool_result": tool_response,
                },
            )
            if isinstance(result.tool_result_mod, dict):
                return result.tool_result_mod
            return None

        return callback

    async def _run_processor_chain(
        self,
        *,
        processors: list[ProcessorInstance],
        harness: HarnessDefinition,
        hook: LifecycleHook,
        state: Any,
        event_data: dict[str, Any],
    ) -> ProcessorResult:
        self._append_lifecycle_record(state, {"hook": hook.value, **event_data})
        aggregate = ProcessorResult(
            allowed_capabilities={capability.value for capability in HOOK_CAPABILITIES[hook]},
            state_delta={},
            metadata={},
        )
        if not processors:
            return aggregate.model_copy(update={"state_delta": None, "metadata": None})

        processor_context = ProcessorContext(
            hook=hook,
            agent_name=harness.agent.name,
            task_id=str(state.get("harness:task_id", "")),
            harness_id=harness.id,
            state=dict(state),
        )
        processor_event = ProcessorEvent(hook=hook, data=event_data)

        for instance in processors:
            result = await self._invoke_processor(instance, processor_context, processor_event)
            aggregate = self._merge_processor_results(aggregate, result)
            if result.metadata:
                self._append_processor_metadata(state, hook, instance.type, result.metadata)
            if result.state_delta:
                self._merge_state(state, result.state_delta)
                processor_context = processor_context.model_copy(update={"state": dict(state)})
            if result.terminate:
                state[PROCESSOR_TERMINATED_KEY] = True
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
        result = self.registry.invoke(instance=instance, context=context, event=event)
        if inspect.isawaitable(result):
            resolved = await result
        else:
            resolved = result
        return cast(ProcessorResult, resolved)

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
        buffer = list(state.get(LIFECYCLE_BUFFER_KEY, []))
        buffer.append(record)
        state[LIFECYCLE_BUFFER_KEY] = buffer

    def _append_processor_metadata(
        self,
        state: Any,
        hook: LifecycleHook,
        processor_name: str,
        metadata: dict[str, Any],
    ) -> None:
        payload = list(state.get(PROCESSOR_METADATA_KEY, []))
        payload.append(
            {
                "hook": hook.value,
                "processor_name": processor_name,
                "metadata": metadata,
            }
        )
        state[PROCESSOR_METADATA_KEY] = payload

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
