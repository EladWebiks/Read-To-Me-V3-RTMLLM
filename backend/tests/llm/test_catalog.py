"""Snapshot catalog: cache semantics, row conversion, query functions."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.models import ModelProvider
from app.modules.llm.registry import MODEL_CATALOG
from app.modules.llm.repository import CatalogRow
from sqlalchemy import select

LITE = "gemini-3.5-flash-lite"


@pytest.fixture(autouse=True)
def _fresh_snapshot() -> Iterator[None]:
    catalog.invalidate()
    yield
    catalog.invalidate()


def _row(
    *,
    provider_name: str = "gemini",
    provider_enabled: bool = True,
    model_name: str = LITE,
    model_enabled: bool = True,
    capabilities: list[str] | None = None,
) -> CatalogRow:
    return CatalogRow(
        provider_name=provider_name,
        provider_enabled=provider_enabled,
        model_name=model_name,
        model_enabled=model_enabled,
        capabilities=capabilities if capabilities is not None else ["FAST_CHAT"],
        context_window=1_000_000,
        supports_tools=True,
        supports_structured=True,
        supports_streaming=True,
        input_cost_per_1m=0.1,
        output_cost_per_1m=0.4,
    )


@pytest.mark.unit
def test_build_snapshot_computes_effective_enabled() -> None:
    specs = catalog.build_snapshot([_row(provider_enabled=False)])
    assert len(specs) == 1
    assert specs[0].enabled is False
    assert specs[0].input_cost_per_1m == 0.1


@pytest.mark.unit
def test_build_snapshot_skips_rows_without_adapter() -> None:
    specs = catalog.build_snapshot([_row(provider_name="openai"), _row()])
    assert [m.provider for m in specs] == ["gemini"]


@pytest.mark.unit
def test_build_snapshot_tolerates_unknown_capability() -> None:
    specs = catalog.build_snapshot([_row(capabilities=["FAST_CHAT", "NOT_A_CAP"])])
    assert specs[0].capabilities == frozenset({ModelCapability.FAST_CHAT})


@pytest.mark.unit
def test_snapshot_expires_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 100.0}
    monkeypatch.setattr("app.modules.llm.catalog.monotonic", lambda: clock["now"])
    catalog.put_snapshot(MODEL_CATALOG)
    assert catalog.current_snapshot() == MODEL_CATALOG
    clock["now"] += catalog.CACHE_TTL_SECONDS + 1
    assert catalog.current_snapshot() == ()


@pytest.mark.unit
def test_cold_snapshot_reads_empty() -> None:
    assert catalog.list_models(enabled_only=False) == []
    assert catalog.get_model("gemini", LITE) is None
    assert catalog.models_for_capability(ModelCapability.FAST_CHAT) == []


@pytest.mark.unit
def test_models_for_capability_prefers_settings_model() -> None:
    catalog.put_snapshot(MODEL_CATALOG)
    matches = catalog.models_for_capability(
        ModelCapability.FAST_CHAT,
        prefer_provider="gemini",
        prefer_model="gemini-3.6-flash",
    )
    assert matches[0].model_name == "gemini-3.6-flash"
    assert len(matches) == 2


@pytest.mark.unit
def test_embedding_has_no_candidate() -> None:
    catalog.put_snapshot(MODEL_CATALOG)
    assert catalog.models_for_capability(ModelCapability.EMBEDDING) == []


@pytest.mark.unit
def test_list_models_enabled_only_filters() -> None:
    disabled = catalog.build_snapshot([_row(model_enabled=False)])
    catalog.put_snapshot(disabled)
    assert catalog.list_models() == []
    assert len(catalog.list_models(enabled_only=False)) == 1


@pytest.mark.integration
async def test_ensure_loaded_reads_seeded_rows(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        specs = await catalog.ensure_loaded(session)
    lite = catalog.get_model("gemini", LITE)
    assert lite is not None
    assert lite.enabled is True
    assert lite.input_cost_per_1m == 0.10
    assert ModelCapability.FAST_CHAT in lite.capabilities
    assert specs == catalog.current_snapshot()


@pytest.mark.integration
async def test_disabled_provider_disables_models(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(ModelProvider).where(ModelProvider.name == "gemini"))
        result.scalar_one().enabled = False
        await session.commit()
    catalog.invalidate()
    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
    assert catalog.models_for_capability(ModelCapability.FAST_CHAT) == []
    assert catalog.list_models(enabled_only=False)  # rows still in the snapshot
