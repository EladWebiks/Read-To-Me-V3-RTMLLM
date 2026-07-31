"""Backoffice membership tier API (needs Postgres)."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.admin.helpers import create_user, login

BASE = "/api/admin/memberships"


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


async def _create_premium(client: AsyncClient) -> None:
    response = await client.post(
        BASE, json={"slug": "premium", "label": "Premium", "rank": 1, "price_label": "$9/mo"}
    )
    assert response.status_code == 200


@pytest.mark.integration
async def test_create_lists_and_seeds_policy_row(client: AsyncClient, admin: UUID) -> None:
    await _create_premium(client)
    listing = await client.get(BASE)
    slugs = {t["slug"]: t for t in listing.json()["memberships"]}
    assert slugs["premium"]["is_active"] is True
    assert slugs["premium"]["user_count"] == 0
    policies = await client.get("/api/admin/membership-policies")
    assert "premium" in {p["membership"] for p in policies.json()["policies"]}


@pytest.mark.integration
async def test_duplicate_slug_409_and_bad_slug_422(client: AsyncClient, admin: UUID) -> None:
    await _create_premium(client)
    dup = await client.post(BASE, json={"slug": "premium", "label": "X"})
    assert dup.status_code == 409
    bad = await client.post(BASE, json={"slug": "Not Valid!", "label": "X"})
    assert bad.status_code == 422


@pytest.mark.integration
async def test_patch_edits_and_crowns_default(client: AsyncClient, admin: UUID) -> None:
    await _create_premium(client)
    patched = await client.patch(f"{BASE}/premium", json={"label": "Premium+", "is_default": True})
    assert patched.status_code == 200
    body = patched.json()
    assert body["label"] == "Premium+"
    assert body["is_default"] is True
    listing = await client.get(BASE)
    free = next(t for t in listing.json()["memberships"] if t["slug"] == "free")
    assert free["is_default"] is False


@pytest.mark.integration
async def test_deactivate_migrates_and_guards(client: AsyncClient, admin: UUID) -> None:
    await _create_premium(client)
    protected = await client.post(f"{BASE}/free/deactivate", json={"migrate_to": "premium"})
    assert protected.status_code == 422  # default tier is protected
    ok = await client.post(f"{BASE}/premium/deactivate", json={"migrate_to": "free"})
    assert ok.status_code == 200
    assert ok.json()["is_active"] is False
    assign = await client.patch(f"/api/admin/users/{admin}", json={"membership": "premium"})
    assert assign.status_code == 404  # inactive tier is not assignable
    unknown = await client.patch(f"{BASE}/ghost", json={"label": "X"})
    assert unknown.status_code == 404


@pytest.mark.integration
async def test_patch_allows_editing_inactive_tier(client: AsyncClient, admin: UUID) -> None:
    """require_tier (edit-path) must accept inactive tiers — the inverse of
    the require_assignable guard covered above. Swapping the two seams at
    any call site should fail this or the deactivate-migrates-and-guards
    test above.
    """
    await _create_premium(client)
    deactivated = await client.post(f"{BASE}/premium/deactivate", json={"migrate_to": "free"})
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    patched = await client.patch(f"{BASE}/premium", json={"label": "Premium (retired)"})
    assert patched.status_code == 200
    body = patched.json()
    assert body["label"] == "Premium (retired)"
    assert body["is_active"] is False
