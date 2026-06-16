# HarnessX Lifecycle → ADK Callback Mapping

## Mapping Table

| HarnessX Hook | ADK Callback | Context Object | Capabilities |
|--------------|-------------|----------------|-------------|
| `TASK_START` | `before_agent_callback` | `CallbackContext` | Set state, attach metadata |
| `STEP_START` | Runner loop (custom) | `InvocationContext` | Increment step counter, emit trace |
| `BEFORE_MODEL` | `before_model_callback` | `CallbackContext` + `LlmRequest` | Modify model request, skip model |
| `AFTER_MODEL` | `after_model_callback` | `CallbackContext` + `LlmResponse` | Modify model response |
| `BEFORE_TOOL` | `before_tool_callback` | `CallbackContext` + tool args | Modify args, block tool |
| `AFTER_TOOL` | `after_model_callback` | `CallbackContext` + tool result | Modify result, record facts |
| `STEP_END` | Runner loop (custom) | `InvocationContext` | Check step budget, detect loops |
| `TASK_END` | `after_agent_callback` | `CallbackContext` | Finalize trace, export metrics |

## Step-Aware Runner Design

ADK's native runner (`runner.run_async()`) streams events but does not expose per-step boundaries. To implement `STEP_START` and `STEP_END` hooks, we wrap the runner in a custom loop:

```python
async def run_with_step_tracking(agent, runner, session, user_input, max_steps, harness):
    step_count = 0
    for step_count in range(1, max_steps + 1):
        # STEP_START: emit trace, run step-start processors
        await emit_step_start(harness, step_count, session)
        
        # Run one ADK turn
        events = []
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=user_input if step_count == 1 else None,
        ):
            events.append(event)
            if event.is_final_response():
                break
        
        # STEP_END: emit trace, run step-end processors
        should_stop = await emit_step_end(harness, step_count, events, session)
        if should_stop:
            break
    
    return events
```

## State Sharing Pattern

Callbacks communicate via ADK session state using prefixed keys:

```
harness:task_id          — current task identifier
harness:family           — task family (account_lookup, policy_question, incident_triage)
harness:step_count       — current step number
harness:tool_calls       — list of tool names called
harness:facts            — extracted facts from tool outputs
harness:trace            — provisional trace data (finalized in TASK_END)
harness:grounding        — grounding information for evaluator
temp:model_request       — ephemeral model request for debugging
```
