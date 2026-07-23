"""Health check schemas."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness payload returned by `/api/health`."""

    status: str = Field(examples=["ok"])
    service: str = Field(examples=["rtm-backend"])
