"""ADK application assembly for compiled harnesses."""

from __future__ import annotations

from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from harness_foundry.runtime.compiler import HarnessCompiler
from harness_foundry.runtime.sessions import create_session_service
from harness_foundry.schema import HarnessDefinition


class ADKApp:
    """Factory for compiled agents and their ADK runners."""

    def __init__(self, compiler: HarnessCompiler):
        self.compiler = compiler

    def create_agent(self, harness: HarnessDefinition) -> LlmAgent:
        """Create the compiled ADK agent."""

        return self.compiler.compile(harness)

    def create_runner(self, harness: HarnessDefinition) -> tuple[Runner, InMemorySessionService]:
        """Create a programmatic ADK runner and its backing session service."""

        agent = self.create_agent(harness)
        session_service = create_session_service()
        runner = Runner(
            agent=agent,
            app_name=f"harness_{harness.id}",
            session_service=session_service,
        )
        return runner, session_service
