"""Unit tests for the health endpoint."""

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    """GET /api/health responds with status ok."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"]
