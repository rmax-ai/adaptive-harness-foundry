"""SQLite-backed trace recorder for normalized lifecycle events."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import structlog

from harness_foundry.schema import TraceEvent

logger = structlog.get_logger()


class TraceRecorder:
    """Records normalized trace events to SQLite and exports JSONL."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(Path(".harness_foundry") / "traces.sqlite3")
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    async def record_event(self, event: TraceEvent) -> None:
        """Persist a single trace event."""

        await self.record_events([event])

    async def record_events(self, events: list[TraceEvent]) -> None:
        """Bulk persist trace events."""

        if not events:
            return
        await asyncio.to_thread(self._record_events_sync, events)

    async def get_run_events(self, run_id: str) -> list[TraceEvent]:
        """Retrieve all events for a run ordered by sequence number."""

        return await asyncio.to_thread(self._get_run_events_sync, run_id)

    async def export_run(self, run_id: str, output_path: str) -> None:
        """Export run events as a JSONL file."""

        events = await self.get_run_events(run_id)
        lines = [event.model_dump_json() for event in events]
        await asyncio.to_thread(Path(output_path).write_text, "\n".join(lines) + "\n", "utf-8")

    def _initialize_database(self) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_events (
                    trace_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    harness_id TEXT NOT NULL,
                    harness_version TEXT NOT NULL,
                    variant_id TEXT,
                    sequence_number INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    hook TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    agent_name TEXT,
                    processor_name TEXT,
                    input_summary TEXT,
                    output_summary TEXT,
                    state_delta TEXT,
                    tool_name TEXT,
                    tool_arguments TEXT,
                    tool_result TEXT,
                    model_name TEXT,
                    token_usage TEXT,
                    latency_ms REAL,
                    error TEXT,
                    metadata TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_trace_events_run_sequence
                ON trace_events(run_id, sequence_number)
                """
            )

    def _record_events_sync(self, events: list[TraceEvent]) -> None:
        rows = [self._to_row(event) for event in events]
        with sqlite3.connect(self._db_path) as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO trace_events (
                    trace_id,
                    run_id,
                    task_id,
                    harness_id,
                    harness_version,
                    variant_id,
                    sequence_number,
                    timestamp,
                    hook,
                    event_type,
                    agent_name,
                    processor_name,
                    input_summary,
                    output_summary,
                    state_delta,
                    tool_name,
                    tool_arguments,
                    tool_result,
                    model_name,
                    token_usage,
                    latency_ms,
                    error,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()

    def _get_run_events_sync(self, run_id: str) -> list[TraceEvent]:
        with sqlite3.connect(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT *
                FROM trace_events
                WHERE run_id = ?
                ORDER BY sequence_number ASC
                """,
                (run_id,),
            ).fetchall()

        return [self._from_row(row) for row in rows]

    def _to_row(self, event: TraceEvent) -> tuple[Any, ...]:
        payload = event.model_dump(mode="json")
        return (
            payload["trace_id"],
            payload["run_id"],
            payload["task_id"],
            payload["harness_id"],
            payload["harness_version"],
            payload["variant_id"],
            payload["sequence_number"],
            payload["timestamp"],
            payload["hook"],
            payload["event_type"],
            payload["agent_name"],
            payload["processor_name"],
            self._json_dumps(payload["input_summary"]),
            self._json_dumps(payload["output_summary"]),
            self._json_dumps(payload["state_delta"]),
            payload["tool_name"],
            self._json_dumps(payload["tool_arguments"]),
            self._json_dumps(payload["tool_result"]),
            payload["model_name"],
            self._json_dumps(payload["token_usage"]),
            payload["latency_ms"],
            self._json_dumps(payload["error"]),
            self._json_dumps(payload["metadata"]),
        )

    def _from_row(self, row: sqlite3.Row) -> TraceEvent:
        return TraceEvent.model_validate(
            {
                "trace_id": row["trace_id"],
                "run_id": row["run_id"],
                "task_id": row["task_id"],
                "harness_id": row["harness_id"],
                "harness_version": row["harness_version"],
                "variant_id": row["variant_id"],
                "sequence_number": row["sequence_number"],
                "timestamp": row["timestamp"],
                "hook": row["hook"],
                "event_type": row["event_type"],
                "agent_name": row["agent_name"],
                "processor_name": row["processor_name"],
                "input_summary": self._json_loads(row["input_summary"]),
                "output_summary": self._json_loads(row["output_summary"]),
                "state_delta": self._json_loads(row["state_delta"]),
                "tool_name": row["tool_name"],
                "tool_arguments": self._json_loads(row["tool_arguments"]),
                "tool_result": self._json_loads(row["tool_result"]),
                "model_name": row["model_name"],
                "token_usage": self._json_loads(row["token_usage"]),
                "latency_ms": row["latency_ms"],
                "error": self._json_loads(row["error"]),
                "metadata": self._json_loads(row["metadata"]) or {},
            }
        )

    def _json_dumps(self, value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, sort_keys=True)

    def _json_loads(self, value: str | None) -> Any:
        if value is None:
            return None
        return json.loads(value)
