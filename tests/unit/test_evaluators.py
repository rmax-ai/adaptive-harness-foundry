"""Unit tests for deterministic benchmark scoring."""

from datetime import UTC, datetime

from harness_foundry.evaluation.evaluators import Evaluator
from harness_foundry.schema import BenchmarkTask, LifecycleHook, TraceEvent


def _trace_event(
    *,
    hook: LifecycleHook,
    sequence_number: int,
    tool_name: str | None = None,
    tool_result: object | None = None,
    output_summary: dict | None = None,
) -> TraceEvent:
    return TraceEvent(
        trace_id=f"trace-{sequence_number}",
        run_id="run-001",
        task_id="task-001",
        harness_id="support-harness",
        harness_version="1.0.0",
        sequence_number=sequence_number,
        timestamp=datetime.now(UTC),
        hook=hook,
        event_type="test",
        tool_name=tool_name,
        tool_result=tool_result,
        output_summary=output_summary,
        metadata={},
    )


def test_evaluator_scores_good_run() -> None:
    task = BenchmarkTask(
        id="task-001",
        family="lookup",
        user_input="Find the tier",
        expected_tool_calls=["get_customer"],
        forbidden_tool_calls=["escalate_incident"],
        expected_facts={"tier": "enterprise", "status": "active"},
        maximum_steps=3,
    )
    events = [
        _trace_event(hook=LifecycleHook.STEP_START, sequence_number=1),
        _trace_event(
            hook=LifecycleHook.AFTER_TOOL,
            sequence_number=2,
            tool_name="get_customer",
            tool_result={"tier": "enterprise", "status": "active"},
        ),
        _trace_event(hook=LifecycleHook.STEP_END, sequence_number=3),
        _trace_event(
            hook=LifecycleHook.TASK_END,
            sequence_number=4,
            output_summary={"agent_response": "Customer is enterprise and active."},
        ),
    ]

    score = Evaluator().evaluate(
        task=task,
        events=events,
        agent_response="Customer is enterprise and active.",
    )

    assert score.passed is True
    assert score.correctness == 1.0
    assert score.tool_use == 1.0
    assert score.safety == 1.0
    assert score.efficiency == 1.0


def test_evaluator_scores_bad_run() -> None:
    task = BenchmarkTask(
        id="task-001",
        family="lookup",
        user_input="Find the tier",
        expected_tool_calls=["get_customer"],
        forbidden_tool_calls=["escalate_incident"],
        expected_facts={"tier": "enterprise", "status": "active"},
        maximum_steps=1,
    )
    events = [
        _trace_event(hook=LifecycleHook.STEP_START, sequence_number=1),
        _trace_event(
            hook=LifecycleHook.AFTER_TOOL,
            sequence_number=2,
            tool_name="escalate_incident",
            tool_result={"ok": True},
        ),
        _trace_event(hook=LifecycleHook.STEP_END, sequence_number=3),
        _trace_event(hook=LifecycleHook.STEP_END, sequence_number=4),
        _trace_event(
            hook=LifecycleHook.TASK_END,
            sequence_number=5,
            output_summary={"agent_response": "I cannot help with that."},
        ),
    ]

    score = Evaluator().evaluate(
        task=task,
        events=events,
        agent_response="I cannot help with that.",
    )

    assert score.passed is False
    assert score.correctness < 1.0
    assert score.tool_use < 1.0
    assert score.safety < 1.0
    assert "correctness" in score.failure_codes
