"""Session helpers for ADK task execution."""

from __future__ import annotations

from typing import Any

from google.adk.sessions.in_memory_session_service import InMemorySessionService

from harness_foundry.runtime.callbacks import LIFECYCLE_BUFFER_KEY
from harness_foundry.schema import BenchmarkTask, HarnessDefinition


def create_session_service() -> InMemorySessionService:
    """Create a new ADK session service."""

    return InMemorySessionService()  # type: ignore[no-untyped-call]


async def init_session_state(
    session_service: InMemorySessionService,
    app_name: str,
    user_id: str,
    session_id: str,
    task: BenchmarkTask,
    harness: HarnessDefinition,
) -> None:
    """Initialize session state with task and harness metadata."""

    state: dict[str, Any] = {
        "harness:task_id": task.id,
        "harness:family": task.family,
        "harness:step_count": 0,
        "harness:tool_calls": [],
        "harness:facts": {},
        "harness:fixture_state": task.fixture_state,
        "harness:id": harness.id,
        "harness:version": harness.version,
        LIFECYCLE_BUFFER_KEY: [],
    }
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state=state,
    )
