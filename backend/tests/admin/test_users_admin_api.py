"""Backoffice user management API (needs Postgres)."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.admin.helpers import create_user, login

BASE = "/api/admin/users"
ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


@pytest.mark.integration
async def test_list_includes_soft_deleted_marked(client: AsyncClient, admin: UUID) -> None:
    await create_user("ghost", deleted=True)
    response = await client.get(BASE)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    ghost = next(u for u in payload["items"] if u["username"] == "ghost")
    assert ghost["deleted_at"] is not None
    boss = next(u for u in payload["items"] if u["username"] == "boss")
    assert boss["deleted_at"] is None
    assert boss["google_linked"] is True


@pytest.mark.integration
async def test_pagination_envelope(client: AsyncClient, admin: UUID) -> None:
    for index in range(3):
        await create_user(f"user-{index}")
    response = await client.get(f"{BASE}?limit=2&offset=0")
    payload = response.json()
    assert payload["total"] == 4
    assert len(payload["items"]) == 2
    assert payload["limit"] == 2
    assert payload["offset"] == 0


@pytest.mark.integration
async def test_promote_then_demote_other_user(client: AsyncClient, admin: UUID) -> None:
    other = await create_user("other")
    up = await client.patch(f"{BASE}/{other}", json={"is_admin": True})
    assert up.status_code == 200
    assert up.json()["is_admin"] is True
    down = await client.patch(f"{BASE}/{other}", json={"is_admin": False})
    assert down.status_code == 200
    assert down.json()["is_admin"] is False


@pytest.mark.integration
async def test_cannot_demote_self(client: AsyncClient, admin: UUID) -> None:
    response = await client.patch(f"{BASE}/{admin}", json={"is_admin": False})
    assert response.status_code == 409


@pytest.mark.integration
async def test_cannot_delete_self(client: AsyncClient, admin: UUID) -> None:
    response = await client.delete(f"{BASE}/{admin}")
    assert response.status_code == 409


@pytest.mark.integration
async def test_delete_other_admin_allowed_when_two(client: AsyncClient, admin: UUID) -> None:
    other = await create_user("other-admin", is_admin=True)
    response = await client.delete(f"{BASE}/{other}")
    assert response.status_code == 200
    assert response.json()["deleted_at"] is not None


@pytest.mark.integration
async def test_soft_delete_then_restore(client: AsyncClient, admin: UUID) -> None:
    target = await create_user("victim")
    deleted = await client.delete(f"{BASE}/{target}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None
    restored = await client.post(f"{BASE}/{target}/restore")
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None


@pytest.mark.integration
async def test_membership_change_valid_and_invalid(client: AsyncClient, admin: UUID) -> None:
    target = await create_user("member")
    ok = await client.patch(f"{BASE}/{target}", json={"membership": "free"})
    assert ok.status_code == 200
    assert ok.json()["membership"] == "free"
    bad = await client.patch(f"{BASE}/{target}", json={"membership": "platinum"})
    assert bad.status_code == 422


@pytest.mark.integration
async def test_unknown_user_404(client: AsyncClient, admin: UUID) -> None:
    response = await client.patch(f"{BASE}/{ZERO}", json={"is_admin": True})
    assert response.status_code == 404
