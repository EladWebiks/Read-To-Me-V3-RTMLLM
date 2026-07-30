"""Admin read/write operations on the DB model catalog (llm module only)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm import catalog
from app.modules.llm.exceptions import (
    AdapterNotRegisteredError,
    CatalogModelNotFoundError,
    CatalogProviderNotFoundError,
    DuplicateCatalogModelError,
)
from app.modules.llm.models import ModelConfiguration, ModelProvider
from app.modules.llm.providers import has_adapter
from app.modules.llm.repository import LlmRepository
from app.modules.llm.schemas import (
    CatalogAdminResponse,
    ModelAdminRead,
    ModelCreate,
    ModelPatch,
    ProviderAdminRead,
)

logger = logging.getLogger(__name__)


class ModelCatalogAdminService:
    """Backoffice catalog management; every write invalidates the snapshot."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = LlmRepository(session)

    async def list_catalog(self) -> CatalogAdminResponse:
        """All providers + models, including unserveable (no-adapter) rows."""
        providers = await self._repo.list_providers()
        by_provider: dict[uuid.UUID, list[ModelConfiguration]] = {}
        for model in await self._repo.list_model_configs():
            by_provider.setdefault(model.provider_id, []).append(model)
        return CatalogAdminResponse(
            providers=[self._provider_read(p, by_provider.get(p.id, [])) for p in providers]
        )

    async def set_provider_enabled(self, name: str, *, enabled: bool) -> ProviderAdminRead:
        """Flip a provider; effective enablement of its models follows."""
        provider = await self._repo.get_provider_by_name(name)
        if provider is None:
            raise CatalogProviderNotFoundError(name)
        provider.enabled = enabled
        await self._session.flush()
        await self._session.refresh(provider)
        catalog.invalidate()
        logger.info("catalog provider updated", extra={"provider": name, "enabled": enabled})
        models = [m for m in await self._repo.list_model_configs() if m.provider_id == provider.id]
        return self._provider_read(provider, models)

    async def patch_model(
        self,
        provider_name: str,
        model_name: str,
        patch: ModelPatch,
    ) -> ModelAdminRead:
        """Partial update: enabled flag and/or unit prices."""
        provider = await self._repo.get_provider_by_name(provider_name)
        if provider is None:
            raise CatalogProviderNotFoundError(provider_name)
        row = await self._repo.get_model_config(provider.id, model_name)
        if row is None:
            raise CatalogModelNotFoundError(f"{provider_name}/{model_name}")
        updates = patch.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in updates.items():
            setattr(row, field, value)
        await self._session.flush()
        await self._session.refresh(row)
        catalog.invalidate()
        logger.info(
            "catalog model updated",
            extra={"provider": provider_name, "model": model_name, "fields": sorted(updates)},
        )
        return self._model_read(provider, row)

    async def create_model(self, data: ModelCreate) -> ModelAdminRead:
        """Add a catalog row for a provider with a registered adapter."""
        if not has_adapter(data.provider):
            raise AdapterNotRegisteredError(data.provider)
        provider = await self._repo.upsert_provider(data.provider)
        if await self._repo.get_model_config(provider.id, data.model_name) is not None:
            raise DuplicateCatalogModelError(f"{data.provider}/{data.model_name}")
        row = ModelConfiguration(
            provider_id=provider.id,
            model_name=data.model_name,
            capabilities=[c.value for c in data.capabilities],
            context_window=data.context_window,
            supports_tools=data.supports_tools,
            supports_structured=data.supports_structured,
            supports_streaming=data.supports_streaming,
            enabled=data.enabled,
            input_cost_per_1m=data.input_cost_per_1m,
            output_cost_per_1m=data.output_cost_per_1m,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        catalog.invalidate()
        logger.info(
            "catalog model created",
            extra={"provider": data.provider, "model": data.model_name},
        )
        return self._model_read(provider, row)

    def _provider_read(
        self,
        provider: ModelProvider,
        models: list[ModelConfiguration],
    ) -> ProviderAdminRead:
        return ProviderAdminRead(
            name=provider.name,
            enabled=provider.enabled,
            has_adapter=has_adapter(provider.name),
            models=[self._model_read(provider, m) for m in models],
        )

    def _model_read(self, provider: ModelProvider, row: ModelConfiguration) -> ModelAdminRead:
        return ModelAdminRead(
            model_name=row.model_name,
            enabled=row.enabled,
            effective_enabled=row.enabled and provider.enabled and has_adapter(provider.name),
            capabilities=sorted(str(c) for c in row.capabilities),
            context_window=row.context_window,
            supports_tools=row.supports_tools,
            supports_structured=row.supports_structured,
            supports_streaming=row.supports_streaming,
            input_cost_per_1m=row.input_cost_per_1m,
            output_cost_per_1m=row.output_cost_per_1m,
            updated_at=row.updated_at,
        )
