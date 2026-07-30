"""401/403 authorization matrix over every backoffice route (needs Postgres).

Every /api/admin route added by a backoffice screen plan MUST register in
ROUTES. With no entries yet, pytest emits one skipped instance per test —
that is expected until the first screen plan lands.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.admin.helpers import create_user, login

ZERO = "00000000-0000-0000-0000-000000000000"

# (method, path, json body) — screen plans append here.
ROUTES: list[tuple[str, str, dict[str, object] | None]] = []


@pytest.mark.integration
@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_anonymous_gets_401(
    client: AsyncClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    response = await client.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_non_admin_gets_403(
    client: AsyncClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    user_id = await create_user("matrix-plain")
    login(client, user_id, "matrix-plain")
    response = await client.request(method, path, json=body)
    assert response.status_code == 403
