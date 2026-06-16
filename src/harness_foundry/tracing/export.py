"""Trace export helpers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from harness_foundry.tracing.redaction import redact_dict, redact_secrets
from harness_foundry.tracing.repository import TraceRepository


async def export_traces(run_id: str, output_path: str, format: str = "jsonl") -> None:
    """Export trace events for a run. Formats: jsonl, json (array)."""

    repository = TraceRepository()
    events = await repository.get_run_events(run_id)
    serialized = [redact_dict(event.model_dump(mode="json")) for event in events]
    destination = Path(output_path)

    if format == "jsonl":
        content = "\n".join(json.dumps(event, sort_keys=True) for event in serialized)
        if content:
            content += "\n"
    elif format == "json":
        content = json.dumps(serialized, indent=2, sort_keys=True) + "\n"
    else:
        raise ValueError(f"Unsupported trace export format: {format}")

    await asyncio.to_thread(destination.write_text, content, "utf-8")


async def export_run_summary(run_id: str, output_path: str) -> None:
    """Export a human-readable summary of a run."""

    repository = TraceRepository()
    events = await repository.get_run_events(run_id)
    failed_task_ids = await repository.get_failed_task_ids(run_id)

    if not events:
        summary = f"Run: {run_id}\nNo trace events found.\n"
        await asyncio.to_thread(Path(output_path).write_text, summary, "utf-8")
        return

    first_event = events[0]
    task_ids = sorted({event.task_id for event in events})
    tool_names = sorted({event.tool_name for event in events if event.tool_name})
    event_types = sorted({event.event_type for event in events})
    lines = [
        f"Run: {run_id}",
        f"Harness: {first_event.harness_id}@{first_event.harness_version}",
        f"Started: {events[0].timestamp.isoformat()}",
        f"Completed: {events[-1].timestamp.isoformat()}",
        f"Tasks: {len(task_ids)}",
        f"Failures: {len(failed_task_ids)}",
        f"Failed Task IDs: {', '.join(failed_task_ids) if failed_task_ids else 'none'}",
        f"Tool Calls: {sum(1 for event in events if event.tool_name)}",
        f"Tools: {', '.join(tool_names) if tool_names else 'none'}",
        f"Event Types: {', '.join(event_types) if event_types else 'none'}",
    ]

    summary = redact_secrets("\n".join(lines) + "\n")
    await asyncio.to_thread(Path(output_path).write_text, summary, "utf-8")
