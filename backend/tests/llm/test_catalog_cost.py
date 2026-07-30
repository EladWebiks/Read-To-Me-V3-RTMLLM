"""Repricing a model in the DB drives unit costs on new cost records."""

from __future__ import annotations

import uuid

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.models import CostRecord, ModelConfiguration
from app.modules.llm.telemetry import LlmTelemetry, NoOpTracer, TelemetryContext
from app.modules.llm.types import Usage
from app.modules.users.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

LITE = "gemini-3.5-flash-lite"


async def _user(session: AsyncSession) -> User:
    """Throwaway owner so the execution's NOT NULL user FK has a target."""
    user = User(username=f"cost-{uuid.uuid4().hex[:10]}", password_hash=None)
    session.add(user)
    await session.flush()
    return user


async def _reprice(*, input_cost: float, output_cost: float) -> None:
    """Reprice directly in the DB — what the admin API does in Task 5."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(ModelConfiguration).where(ModelConfiguration.model_name == LITE)
        )
        row = result.scalar_one()
        row.input_cost_per_1m = input_cost
        row.output_cost_per_1m = output_cost
        await session.commit()
    catalog.invalidate()


@pytest.mark.integration
async def test_repriced_model_drives_cost_records(seeded_catalog: None) -> None:
    await _reprice(input_cost=1.0, output_cost=2.0)

    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
        model = catalog.get_model("gemini", LITE)
        assert model is not None
        assert model.input_cost_per_1m == 1.0

        user = await _user(session)
        telemetry = LlmTelemetry(session, NoOpTracer())
        context = TelemetryContext(
            task="cost-test",
            model=model,
            fallback_used=False,
            user_id=user.id,
        )

        async def _call() -> tuple[str, Usage]:
            return "ok", Usage(1_000_000, 1_000_000)

        await telemetry.record_call(context, _call)

        result = await session.execute(
            select(CostRecord).order_by(CostRecord.created_at.desc()).limit(1)
        )
        record = result.scalar_one()
        assert record.unit_cost_in == 1.0
        assert record.unit_cost_out == 2.0
        assert record.total_cost == pytest.approx(3.0)
