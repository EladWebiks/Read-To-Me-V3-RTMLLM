"""Discovery HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.modules.discovery.schemas import DiscoverySearchResponse
from app.modules.discovery.service import DiscoveryService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/search", response_model=DiscoverySearchResponse)
async def search_discovered_books(
    q: str = Query(min_length=1, max_length=200),
    external: bool = Query(default=True),
    user: UserRead = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DiscoverySearchResponse:
    return await DiscoveryService(session).search_by_title(
        user.id,
        q,
        external=external,
    )
