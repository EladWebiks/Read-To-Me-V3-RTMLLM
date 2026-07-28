"""Seed model_providers / model_configurations from the static registry."""

from __future__ import annotations

from app.core.db import SessionLocal
from app.modules.llm.models import ModelProvider
from app.modules.llm.registry import MODEL_CATALOG
from app.modules.llm.repository import LlmRepository


async def seed_llm_models() -> None:
    """Upsert catalog rows if missing."""
    async with SessionLocal() as session:
        repo = LlmRepository(session)
        providers: dict[str, ModelProvider] = {}
        for spec in MODEL_CATALOG:
            if spec.provider not in providers:
                providers[spec.provider] = await repo.upsert_provider(spec.provider)
            await repo.upsert_model(providers[spec.provider], spec)
        await session.commit()
