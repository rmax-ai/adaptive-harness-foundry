"""Integration tests for harness compilation into ADK agents."""

from harness_foundry.runtime.compiler import HarnessCompiler
from harness_foundry.schema import AgentConfig, HarnessDefinition, ModelConfig, ToolPolicy


def test_compiler_creates_llm_agent_with_expected_fields() -> None:
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
            instruction_append="Use tools when needed.",
            maximum_steps=4,
        ),
        tools=ToolPolicy(allow=["get_customer", "search_policy"]),
        processors={},
    )

    agent = HarnessCompiler().compile(harness)

    assert agent.name == "support_agent"
    assert "Help the user." in agent.instruction
    assert "Use tools when needed." in agent.instruction
    assert len(agent.tools) == 2
    assert {tool.__name__ for tool in agent.tools} == {"get_customer", "search_policy"}
