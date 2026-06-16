"""Integration tests for task execution and trace emission."""

from google.adk.agents.llm_agent import LlmAgent
from google.genai import types

from harness_foundry.runtime import ADKApp, HarnessCompiler, TaskRunner
from harness_foundry.schema import (
    AgentConfig,
    BenchmarkTask,
    HarnessDefinition,
    ModelConfig,
    ToolPolicy,
)
from harness_foundry.tracing import TraceRecorder


async def test_task_runner_emits_trace_events_for_fake_model(tmp_path) -> None:
    harness = HarnessDefinition(
        id="support-harness",
        version="1.0.0",
        parent_version=None,
        author="human",
        task_family="default",
        status="active",
        model=ModelConfig(provider="google", model="gemini-2.0-flash"),
        agent=AgentConfig(
            name="support_agent",
            instruction="Help the user.",
            maximum_steps=3,
        ),
        tools=ToolPolicy(allow=[]),
        processors={},
    )
    task = BenchmarkTask(
        id="task-001",
        family="lookup",
        user_input="Hello",
        expected_tool_calls=[],
        forbidden_tool_calls=[],
        expected_facts={"message_contains": "deterministic reply"},
        maximum_steps=3,
    )

    compiler = HarnessCompiler()

    def fake_compile(_: HarnessDefinition) -> LlmAgent:
        async def before_model(*, callback_context, llm_request):
            from google.adk.models.llm_response import LlmResponse

            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="deterministic reply")],
                )
            )

        return LlmAgent(
            name="support_agent",
            model="gemini-2.0-flash",
            instruction="Help the user.",
            before_model_callback=before_model,
        )

    compiler.compile = fake_compile  # type: ignore[method-assign]
    tracer = TraceRecorder(db_path=str(tmp_path / "traces.sqlite3"))
    runner = TaskRunner(app=ADKApp(compiler=compiler), tracer=tracer)

    events = await runner.run_task(harness=harness, task=task, run_id="run-001")

    hooks = [event.hook for event in events]
    assert hooks[0].value == "TASK_START"
    assert hooks[-1].value == "TASK_END"
    assert any(event.hook.value == "STEP_START" for event in events)
    assert any(event.hook.value == "STEP_END" for event in events)
    assert events[-1].output_summary == {"agent_response": "deterministic reply"}

    persisted = await tracer.get_run_events("run-001")
    assert len(persisted) == len(events)
