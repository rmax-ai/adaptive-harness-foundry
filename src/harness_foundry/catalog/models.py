"""SQLAlchemy models for catalog persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for catalog ORM models."""


class HarnessVersionModel(Base):
    """Persisted harness configuration version."""

    __tablename__ = "harness_versions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    config_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    author: Mapped[str] = mapped_column(String(16))
    task_family: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    parent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class PromotionRecordModel(Base):
    """Persisted promotion decision between a baseline and candidate harness."""

    __tablename__ = "promotion_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    baseline_id: Mapped[str] = mapped_column(String(128))
    baseline_version: Mapped[str] = mapped_column(String(32))
    candidate_id: Mapped[str] = mapped_column(String(128))
    candidate_version: Mapped[str] = mapped_column(String(32))
    baseline_hash: Mapped[str] = mapped_column(String(64))
    candidate_hash: Mapped[str] = mapped_column(String(64))
    patch_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    gate_results: Mapped[dict[str, Any]] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
