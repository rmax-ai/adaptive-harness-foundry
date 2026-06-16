"""Async repository for harness catalog persistence."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from harness_foundry.catalog.models import Base, HarnessVersionModel, PromotionRecordModel
from harness_foundry.schema import HarnessDefinition
from harness_foundry.settings import DATABASE_URL


class CatalogRepository:
    """Persistence adapter for harness catalog operations."""

    def __init__(self, db_url: str | None = None):
        resolved_db_url = db_url or DATABASE_URL or "sqlite:///data/harness_foundry.db"
        self._db_url = self._normalize_database_url(resolved_db_url)
        self._engine: AsyncEngine = create_async_engine(self._db_url)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init(self) -> None:
        """Create catalog tables if they do not exist."""

        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def save_harness(self, harness: HarnessDefinition) -> None:
        """Save a harness definition. Raises if hash already exists."""

        async with self._session_factory() as session:
            session.add(self._to_harness_model(harness))
            await self._commit(session)

    async def get_harness(self, harness_id: str, version: str) -> HarnessDefinition | None:
        """Return a single harness version when present."""

        async with self._session_factory() as session:
            model = await session.get(HarnessVersionModel, {"id": harness_id, "version": version})
            if model is None:
                return None
            return HarnessDefinition.model_validate(model.config_json)

    async def list_harnesses(self, harness_id: str | None = None) -> list[HarnessVersionModel]:
        """List persisted harness records."""

        async with self._session_factory() as session:
            statement = select(HarnessVersionModel).order_by(
                HarnessVersionModel.id,
                HarnessVersionModel.created_at.desc(),
            )
            if harness_id is not None:
                statement = statement.where(HarnessVersionModel.id == harness_id)
            result = await session.scalars(statement)
            return list(result)

    async def get_active_harness(self, harness_id: str) -> HarnessDefinition | None:
        """Return the active harness version for an ID when present."""

        async with self._session_factory() as session:
            statement = (
                select(HarnessVersionModel)
                .where(
                    HarnessVersionModel.id == harness_id,
                    HarnessVersionModel.status == "active",
                )
                .order_by(HarnessVersionModel.created_at.desc())
                .limit(1)
            )
            model = await session.scalar(statement)
            if model is None:
                return None
            return HarnessDefinition.model_validate(model.config_json)

    async def update_harness(self, harness: HarnessDefinition) -> None:
        """Persist a replacement configuration for an existing harness version."""

        async with self._session_factory() as session:
            model = await session.get(
                HarnessVersionModel, {"id": harness.id, "version": harness.version}
            )
            if model is None:
                raise LookupError(f"Harness {harness.id} v{harness.version} was not found.")

            model.config_hash = harness.config_hash()
            model.config_json = harness.model_dump(mode="json")
            model.author = harness.author
            model.task_family = harness.task_family
            model.status = harness.status
            model.parent_version = harness.parent_version
            await self._commit(session)

    async def save_promotion(self, record: PromotionRecordModel) -> None:
        """Persist a promotion decision record."""

        async with self._session_factory() as session:
            persisted = PromotionRecordModel(
                baseline_id=record.baseline_id,
                baseline_version=record.baseline_version,
                candidate_id=record.candidate_id,
                candidate_version=record.candidate_version,
                baseline_hash=record.baseline_hash,
                candidate_hash=record.candidate_hash,
                patch_json=record.patch_json,
                gate_results=record.gate_results,
                decision=record.decision,
            )
            session.add(persisted)
            await self._commit(session)

    async def list_promotions(self, harness_id: str) -> list[PromotionRecordModel]:
        """List promotion records associated with a harness ID."""

        async with self._session_factory() as session:
            statement = (
                select(PromotionRecordModel)
                .where(
                    or_(
                        PromotionRecordModel.baseline_id == harness_id,
                        PromotionRecordModel.candidate_id == harness_id,
                    )
                )
                .order_by(PromotionRecordModel.created_at.desc(), PromotionRecordModel.id.desc())
            )
            result = await session.scalars(statement)
            return list(result)

    def _to_harness_model(self, harness: HarnessDefinition) -> HarnessVersionModel:
        return HarnessVersionModel(
            id=harness.id,
            version=harness.version,
            config_hash=harness.config_hash(),
            config_json=harness.model_dump(mode="json"),
            author=harness.author,
            task_family=harness.task_family,
            status=harness.status,
            parent_version=harness.parent_version,
            rationale=None,
            evidence_refs=None,
        )

    async def _commit(self, session: AsyncSession) -> None:
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise

    def _normalize_database_url(self, db_url: str) -> str:
        if db_url.startswith("sqlite+aiosqlite:///"):
            return db_url
        if db_url.startswith("sqlite:///"):
            return db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return db_url
