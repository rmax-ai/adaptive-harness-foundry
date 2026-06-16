# ADR 0001: Google ADK v2 as Runtime Engine

**Date:** 2026-06-16
**Status:** Accepted
**Author:** Max Espinoza

## Context

The Adaptive Harness Foundry needs an LLM agent runtime that can:
1. Execute tools based on natural language instructions
2. Expose lifecycle hooks for pre/post model and pre/post tool interception
3. Support programmatic invocation (not just chat)
4. Provide structured session state for sharing context between callbacks and tools
5. Run with Gemini models (default) or deterministic fake models (testing)

## Decision

Use **Google ADK Python v2.2+** as the runtime engine. Do not wrap it in unnecessary abstractions.

## Alternatives Considered

| Option | Rejected Because |
|--------|-----------------|
| Custom agent loop | Reinvents ADK's mature concurrency, streaming, and error handling |
| LangChain/LangGraph | Heavier dependency, different callback model, ADK has first-class Gemini integration |
| Claude SDK / Anthropic-only | Spec requires Gemini default; ADK is model-agnostic with Gemini-native optimization |

## Consequences

### Positive
- ADK v2 callbacks (`before_model`, `after_model`, `before_tool`, `after_tool`, `before_agent`, `after_agent`) map cleanly to HarnessX lifecycle hooks
- `LlmAgent` constructor accepts tools as plain Python functions — no adapter needed
- Session state accessible from both callbacks (`CallbackContext`) and tools (`ToolContext`)
- `InMemoryRunner` provides programmatic invocation with `AsyncGenerator[Event]` output
- Official support from Google, 20K+ GitHub stars, bi-weekly release cadence

### Negative
- ADK v2 deprecated `SequentialAgent`, `ParallelAgent`, `LoopAgent` — replaced by newer `Workflow` graph API (still maturing)
- For deterministic orchestration, we must subclass `BaseAgent` and override `_run_async_impl`
- No built-in fake model for testing — must implement via `before_model_callback` mock
- Breaking changes from v1.x require awareness during implementation

## Implementation Notes

- HarnessX lifecycle hooks map to ADK callbacks:
  - `TASK_START` → `before_agent_callback`
  - `STEP_START` → Handled in our runner loop (ADK doesn't expose per-step lifecycle natively)
  - `BEFORE_MODEL` → `before_model_callback`
  - `AFTER_MODEL` → `after_model_callback`
  - `BEFORE_TOOL` → `before_tool_callback`
  - `AFTER_TOOL` → `after_tool_callback`
  - `STEP_END` → Handled in our runner loop
  - `TASK_END` → `after_agent_callback`

- `STEP_START` and `STEP_END` require wrapping the ADK runner in a step-aware loop that injects state and emits trace events between LLM calls

- For deterministic testing, implement a `before_model_callback` that returns canned `LlmResponse` objects based on the `LlmRequest` content — this completely bypasses the LLM while exercising the full callback chain
