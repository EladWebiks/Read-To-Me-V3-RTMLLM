"""Admin catalog CRUD (backoffice). HTTP only; logic in ModelCatalogAdminService."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.llm.catalog_service import ModelCatalogAdminService
from app.modules.llm.schemas import (
    CatalogAdminResponse,
    ModelAdminRead,
    ModelCreate,
    ModelPatch,
    ProviderAdminRead,
    ProviderPatch,
)
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin/llm", tags=["admin"])


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> ModelCatalogAdminService:
    return ModelCatalogAdminService(session)


@router.get("/catalog")
async def get_catalog(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ModelCatalogAdminService, Depends(_service)],
) -> CatalogAdminResponse:
    """Providers + models with enabled state, adapter presence, and pricing."""
    return await service.list_catalog()


@router.patch("/catalog/providers/{provider}")
async def patch_provider(
    provider: str,
    body: ProviderPatch,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ModelCatalogAdminService, Depends(_service)],
) -> ProviderAdminRead:
    """Enable/disable a provider (its models follow effectively)."""
    return await service.set_provider_enabled(provider, enabled=body.enabled)


@router.patch("/catalog/models/{provider}/{model_name}")
async def patch_model(
    provider: str,
    model_name: str,
    body: ModelPatch,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ModelCatalogAdminService, Depends(_service)],
) -> ModelAdminRead:
    """Partially update one model (enabled, pricing)."""
    return await service.patch_model(provider, model_name, body)


@router.post("/catalog/models", status_code=201)
async def create_model(
    body: ModelCreate,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ModelCatalogAdminService, Depends(_service)],
) -> ModelAdminRead:
    """Add a catalog model for a provider with a registered adapter."""
    return await service.create_model(body)
