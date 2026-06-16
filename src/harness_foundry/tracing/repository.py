"""Query helpers for persisted trace events."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from harness_foundry import settings
from harness_foundry.schema import TraceEvent, TraceRun

_DEFAULT_TRACE_DB_PATH = str(Path(".harness_foundry") / "traces.sqlite3")


class TraceRepository:
    """Query interface for persisted trace events."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or getattr(settings, "TRACE_DB_PATH", _DEFAULT_TRACE_DB_PATH)

    async def get_run_events(self, run_id: str) -> list[TraceEvent]:
        """Return all events for a run ordered by sequence number."""

        return await asyncio.to_thread(self._get_run_events_sync, run_id)

    async def get_failed_task_ids(self, run_id: str) -> list[str]:
        """Return task ids that ended in failure for a run."""

        return await asyncio.to_thread(self._get_failed_task_ids_sync, run_id)

    async def get_task_events(self, run_id: str, task_id: str) -> list[TraceEvent]:
        """Return all events for a task within a run."""

        return await asyncio.to_thread(self._get_task_events_sync, run_id, task_id)

    async def get_tool_calls(self, run_id: str, task_id: str) -> list[dict]:
        """Return normalized tool call records for a task."""

        return await asyncio.to_thread(self._get_tool_calls_sync, run_id, task_id)

    async def list_runs(
        self,
        harness_id: str | None = None,
        limit: int = 50,
    ) -> list[TraceRun]:
        """Return recent runs derived from persisted trace events."""

        return await asyncio.to_thread(self._list_runs_sync, harness_id, limit)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _get_run_events_sync(self, run_id: str) -> list[TraceEvent]:
        with self._connect() as connection:
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

    def _get_failed_task_ids_sync(self, run_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT task_id
                FROM trace_events
                WHERE run_id = ?
                  AND hook = 'TASK_END'
                  AND event_type = 'task_failed'
                ORDER BY task_id ASC
                """,
                (run_id,),
            ).fetchall()
        return [str(row["task_id"]) for row in rows]

    def _get_task_events_sync(self, run_id: str, task_id: str) -> list[TraceEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM trace_events
                WHERE run_id = ?
                  AND task_id = ?
                ORDER BY sequence_number ASC
                """,
                (run_id, task_id),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _get_tool_calls_sync(self, run_id: str, task_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    trace_id,
                    sequence_number,
                    timestamp,
                    event_type,
                    tool_name,
                    tool_arguments,
                    tool_result,
                    latency_ms,
                    error,
                    metadata
                FROM trace_events
                WHERE run_id = ?
                  AND task_id = ?
                  AND tool_name IS NOT NULL
                  AND hook IN ('BEFORE_TOOL', 'AFTER_TOOL')
                ORDER BY sequence_number ASC
                """,
                (run_id, task_id),
            ).fetchall()

        tool_calls = []
        for row in rows:
            tool_calls.append(
                {
                    "trace_id": row["trace_id"],
                    "sequence_number": row["sequence_number"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "tool_name": row["tool_name"],
                    "tool_arguments": self._json_loads(row["tool_arguments"]),
                    "tool_result": self._json_loads(row["tool_result"]),
                    "latency_ms": row["latency_ms"],
                    "error": self._json_loads(row["error"]),
                    "metadata": self._json_loads(row["metadata"]) or {},
                }
            )
        return tool_calls

    def _list_runs_sync(self, harness_id: str | None, limit: int) -> list[TraceRun]:
        filters = []
        parameters: list[Any] = []
        if harness_id is not None:
            filters.append("harness_id = ?")
            parameters.append(harness_id)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        parameters.append(limit)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    run_id,
                    harness_id,
                    harness_version,
                    COALESCE(
                        MAX(CASE WHEN json_extract(metadata, '$.split') IS NOT NULL
                            THEN json_extract(metadata, '$.split')
                        END),
                        'unknown'
                    ) AS split,
                    MIN(timestamp) AS started_at,
                    MAX(CASE WHEN hook = 'TASK_END' THEN timestamp END) AS completed_at,
                    COUNT(DISTINCT task_id) AS task_count
                FROM trace_events
                {where_clause}
                GROUP BY run_id, harness_id, harness_version
                ORDER BY started_at DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()

        return [
            TraceRun.model_validate(
                {
                    "run_id": row["run_id"],
                    "harness_id": row["harness_id"],
                    "harness_version": row["harness_version"],
                    "split": row["split"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "task_count": row["task_count"],
                }
            )
            for row in rows
        ]

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

    def _json_loads(self, value: str | None) -> Any:
        if value is None:
            return None
        return json.loads(value)
