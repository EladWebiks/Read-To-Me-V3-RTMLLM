"""Backoffice aggregation router — thin composition over owning modules.

Screen plans register their sub-routers here (users, usage, tool-calls,
jobs). The aggregator itself defines no endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.admin.usage_router import router as usage_router
from app.modules.admin.users_router import router as users_router

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(users_router)
router.include_router(usage_router)
