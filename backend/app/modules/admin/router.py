"""Backoffice aggregation router — thin composition over owning modules.

Screen plans register their sub-routers here (users, usage, tool-calls,
jobs). The aggregator itself defines no endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
