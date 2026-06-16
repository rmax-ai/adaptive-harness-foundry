"""Task execution wrapper around ADK runners."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.genai import types

from harness_foundry.runtime.adk_app import ADKApp
from harness_foundry.schema import (
    BenchmarkTask,
    ErrorRecord,
    HarnessDefinition,
    LifecycleHook,
    TraceEvent,
)
from harness_foundry.tracing.recorder import TraceRecorder

logger = structlog.get_logger()

_LIFECYCLE_BUFFER_KEY = "harness_foundry:lifecycle_buffer"


class TaskRunner:
    """Runs benchmark tasks against a harness while collecting normalized trace events."""

    def __init__(self, app: ADKApp, tracer: TraceRecorder):
        self._app = app
        self._tracer = tracer

    async def run_task(
        self,
        harness: HarnessDefinition,
        task: BenchmarkTask,
        run_id: str,
    ) -> list[TraceEvent]:
        """Run a single benchmark task and persist the resulting trace events."""

        runner, session_service = self._app.create_runner(harness)
        app_name = self._app_name(harness, runner)
        session_id = f"{run_id}:{task.id}"
        initial_state = {
            "harness:task_id": task.id,
            "harness:family": task.family,
            "harness:step_count": 0,
            "harness:fixture_state": task.fixture_state,
            _LIFECYCLE_BUFFER_KEY: [],
        }
        await session_service.create_session(
            app_name=app_name,
            user_id=run_id,
            session_id=session_id,
            state=initial_state,
        )

        trace_events: list[TraceEvent] = []
        sequence_number = 0

        def append_event(
            *,
            hook: LifecycleHook,
            event_type: str,
            input_summary: dict[str, Any] | None = None,
            output_summary: dict[str, Any] | None = None,
            state_delta: dict[str, Any] | None = None,
            tool_name: str | None = None,
            tool_arguments: dict[str, Any] | None = None,
            tool_result: Any | None = None,
            metadata: dict[str, Any] | None = None,
            error: ErrorRecord | None = None,
        ) -> None:
            nonlocal sequence_number
            sequence_number += 1
            trace_events.append(
                TraceEvent(
                    trace_id=str(uuid4()),
                    run_id=run_id,
                    task_id=task.id,
                    harness_id=harness.id,
                    harness_version=harness.version,
                    sequence_number=sequence_number,
                    timestamp=datetime.now(UTC),
                    hook=hook,
                    event_type=event_type,
                    agent_name=harness.agent.name,
                    input_summary=input_summary,
                    output_summary=output_summary,
                    state_delta=state_delta,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments,
                    tool_result=tool_result,
                    model_name=harness.model.model,
                    error=error,
                    metadata=metadata or {},
                )
            )

        append_event(
            hook=LifecycleHook.TASK_START,
            event_type="task_started",
            input_summary={"user_input": task.user_input},
            metadata={"family": task.family},
        )
        append_event(
            hook=LifecycleHook.STEP_START,
            event_type="step_started",
            metadata={"step_number": 1},
        )

        adk_events: list[Event] = []
        task_error: Exception | None = None
        try:
            async for event in runner.run_async(
                user_id=run_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=task.user_input)]),
            ):
                adk_events.append(event)
        except Exception as exc:
            task_error = exc
            logger.exception(
                "task_runner_failed",
                harness_id=harness.id,
                task_id=task.id,
                run_id=run_id,
            )

        session = await session_service.get_session(
            app_name=app_name,
            user_id=run_id,
            session_id=session_id,
        )
        session_state = session.state if session is not None else {}
        lifecycle_records = list(session_state.get(_LIFECYCLE_BUFFER_KEY, []))
        self._append_lifecycle_trace_events(
            append_event=append_event,
            lifecycle_records=lifecycle_records,
            harness=harness,
        )

        step_number = 1
        for index, event in enumerate(adk_events):
            next_event = adk_events[index + 1] if index + 1 < len(adk_events) else None

            for function_call in event.get_function_calls():
                append_event(
                    hook=LifecycleHook.BEFORE_TOOL,
                    event_type="tool_requested",
                    tool_name=function_call.name,
                    tool_arguments=dict(function_call.args or {}),
                    metadata={"step_number": step_number},
                )

            for function_response in event.get_function_responses():
                append_event(
                    hook=LifecycleHook.AFTER_TOOL,
                    event_type="tool_completed",
                    tool_name=function_response.name,
                    tool_result=function_response.response,
                    metadata={"step_number": step_number},
                )
                append_event(
                    hook=LifecycleHook.STEP_END,
                    event_type="step_completed",
                    output_summary={"reason": "tool_response"},
                    metadata={"step_number": step_number},
                )
                if next_event is not None:
                    step_number += 1
                    append_event(
                        hook=LifecycleHook.STEP_START,
                        event_type="step_started",
                        metadata={"step_number": step_number},
                    )

            if event.is_final_response():
                append_event(
                    hook=LifecycleHook.STEP_END,
                    event_type="step_completed",
                    output_summary={"reason": "final_response"},
                    metadata={"step_number": step_number},
                )

        final_response = self._extract_final_response(adk_events)
        final_metadata = {
            "family": task.family,
            "step_count": step_number,
            "adk_event_count": len(adk_events),
        }
        if step_number > harness.agent.maximum_steps:
            final_metadata["maximum_steps_exceeded"] = True

        append_event(
            hook=LifecycleHook.TASK_END,
            event_type="task_completed" if task_error is None else "task_failed",
            output_summary={"agent_response": final_response},
            metadata=final_metadata,
            error=(
                ErrorRecord(code="task_runner_error", message=str(task_error))
                if task_error is not None
                else None
            ),
        )

        await self._tracer.record_events(trace_events)

        if task_error is not None:
            raise task_error

        return trace_events

    def _append_lifecycle_trace_events(
        self,
        *,
        append_event: Any,
        lifecycle_records: list[dict[str, Any]],
        harness: HarnessDefinition,
    ) -> None:
        for record in lifecycle_records:
            hook = LifecycleHook(record["hook"])
            if hook in {LifecycleHook.TASK_START, LifecycleHook.TASK_END}:
                continue

            append_event(
                hook=hook,
                event_type=f"{hook.value.lower()}_callback",
                input_summary={
                    key: value
                    for key, value in record.items()
                    if key not in {"hook", "tool_name", "tool_arguments", "tool_result"}
                }
                or None,
                tool_name=record.get("tool_name"),
                tool_arguments=record.get("tool_arguments"),
                tool_result=record.get("tool_result"),
                metadata={"source": "callback", "agent_name": harness.agent.name},
            )

    def _extract_final_response(self, events: list[Event]) -> str:
        for event in reversed(events):
            if not event.is_final_response() or event.content is None or not event.content.parts:
                continue

            texts = [part.text for part in event.content.parts if part.text]
            if texts:
                return "\n".join(texts)
        return ""

    def _app_name(self, harness: HarnessDefinition, runner: Runner) -> str:
        app_name = getattr(runner, "app_name", None)
        if isinstance(app_name, str) and app_name:
            return app_name
        return f"harness_{harness.id}"
