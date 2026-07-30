"""Seed semantics: pricing on insert; restart never overwrites admin edits."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.core.db import SessionLocal
from app.modules.llm.models import ModelConfiguration
from app.modules.llm.seed import seed_llm_models
from sqlalchemy import select, text

LITE = "gemini-3.5-flash-lite"


async def _reset_catalog_rows() -> None:
    async with SessionLocal() as session:
        await session.execute(text("DELETE FROM model_configurations"))
        await session.execute(text("DELETE FROM model_providers"))
        await session.commit()


@pytest.fixture
async def pristine_catalog() -> AsyncIterator[None]:
    """Empty catalog tables before the test; restore seeded defaults after."""
    await _reset_catalog_rows()
    yield
    await _reset_catalog_rows()
    await seed_llm_models()


async def _flash_lite_row() -> ModelConfiguration:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ModelConfiguration).where(ModelConfiguration.model_name == LITE)
        )
        return result.scalar_one()


@pytest.mark.integration
async def test_seed_inserts_pricing(pristine_catalog: None) -> None:
    await seed_llm_models()
    row = await _flash_lite_row()
    assert row.input_cost_per_1m == 0.10
    assert row.output_cost_per_1m == 0.40
    assert row.updated_at is not None


@pytest.mark.integration
async def test_reseed_never_overwrites_admin_edits(pristine_catalog: None) -> None:
    await seed_llm_models()
    async with SessionLocal() as session:
        result = await session.execute(
            select(ModelConfiguration).where(ModelConfiguration.model_name == LITE)
        )
        row = result.scalar_one()
        row.enabled = False
        row.input_cost_per_1m = 9.99
        await session.commit()
    await seed_llm_models()
    row = await _flash_lite_row()
    assert row.enabled is False
    assert row.input_cost_per_1m == 9.99
