"""ModelCatalogAdminService: list/patch/create with snapshot invalidation."""

from __future__ import annotations

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.catalog_service import ModelCatalogAdminService
from app.modules.llm.exceptions import (
    AdapterNotRegisteredError,
    CatalogModelNotFoundError,
    CatalogProviderNotFoundError,
    DuplicateCatalogModelError,
)
from app.modules.llm.schemas import ModelCreate, ModelPatch
from pydantic import ValidationError

LITE = "gemini-3.5-flash-lite"


def _create(*, provider: str = "gemini", model_name: str = "gemini-x") -> ModelCreate:
    return ModelCreate(
        provider=provider,
        model_name=model_name,
        capabilities=[ModelCapability.FAST_CHAT],
        context_window=100_000,
        input_cost_per_1m=0.2,
        output_cost_per_1m=0.8,
    )


@pytest.mark.integration
async def test_list_catalog_shows_seeded_rows(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        listing = await ModelCatalogAdminService(session).list_catalog()
    gemini = next(p for p in listing.providers if p.name == "gemini")
    assert gemini.has_adapter is True
    lite = next(m for m in gemini.models if m.model_name == LITE)
    assert lite.effective_enabled is True
    assert lite.input_cost_per_1m == 0.10


@pytest.mark.integration
async def test_disable_provider_cascades(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        provider = await ModelCatalogAdminService(session).set_provider_enabled(
            "gemini", enabled=False
        )
        await session.commit()
    assert all(m.effective_enabled is False for m in provider.models)
    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
    assert catalog.models_for_capability(ModelCapability.FAST_CHAT) == []


@pytest.mark.integration
async def test_patch_model_reprices_and_disables(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        updated = await ModelCatalogAdminService(session).patch_model(
            "gemini", LITE, ModelPatch(enabled=False, input_cost_per_1m=1.5)
        )
        await session.commit()
    assert updated.enabled is False
    assert updated.input_cost_per_1m == 1.5
    assert updated.output_cost_per_1m == 0.40  # untouched field stays
    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
    spec = catalog.get_model("gemini", LITE)
    assert spec is not None
    assert spec.enabled is False
    assert spec.input_cost_per_1m == 1.5


@pytest.mark.integration
async def test_unknown_targets_raise(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        service = ModelCatalogAdminService(session)
        with pytest.raises(CatalogProviderNotFoundError):
            await service.patch_model("nope", LITE, ModelPatch(enabled=True))
        with pytest.raises(CatalogModelNotFoundError):
            await service.patch_model("gemini", "nope", ModelPatch(enabled=True))
        with pytest.raises(CatalogProviderNotFoundError):
            await service.set_provider_enabled("nope", enabled=False)


@pytest.mark.integration
async def test_create_model_validates_adapter_and_duplicates(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        service = ModelCatalogAdminService(session)
        with pytest.raises(AdapterNotRegisteredError):
            await service.create_model(_create(provider="openai"))
        with pytest.raises(DuplicateCatalogModelError):
            await service.create_model(_create(model_name=LITE))
        created = await service.create_model(_create(model_name="gemini-3.7-pro"))
        await session.commit()
    assert created.effective_enabled is True
    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
    assert catalog.get_model("gemini", "gemini-3.7-pro") is not None


@pytest.mark.unit
def test_model_create_rejects_unknown_capability() -> None:
    with pytest.raises(ValidationError):
        ModelCreate.model_validate(
            {
                "provider": "gemini",
                "model_name": "m",
                "capabilities": ["NOT_A_CAPABILITY"],
                "context_window": 1,
            }
        )


@pytest.mark.unit
def test_model_patch_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        ModelPatch(input_cost_per_1m=-0.1)
