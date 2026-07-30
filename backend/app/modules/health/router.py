"""Health check HTTP routes."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.modules.health.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return API liveness status."""
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app.name)
