"""Backoffice usage/cost aggregates against seeded rows (needs Postgres)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.admin.helpers import create_user, login, roll_days, seed_execution

FROM = datetime(2026, 7, 1, tzinfo=UTC)
TO = datetime(2026, 8, 1, tzinfo=UTC)
PERIOD = {"from": "2026-07-01T00:00:00Z", "to": "2026-08-01T00:00:00Z"}


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


@pytest.fixture
async def seeded(admin: UUID) -> tuple[UUID, UUID]:
    """Known sums: alice 300/30 tokens $0.75 (2 execs), bob 400/40 $1.00 (1 exec).

    A row exactly at `from` is included; a row exactly at `to` is excluded.
    """
    alice = await create_user("alice")
    bob = await create_user("bob")
    await seed_execution(
        alice, created_at=FROM, model="m1", task="chat", tokens_in=100, tokens_out=10, cost=0.5
    )
    await seed_execution(
        alice,
        created_at=datetime(2026, 7, 20, tzinfo=UTC),
        model="m2",
        task="summarize",
        tokens_in=200,
        tokens_out=20,
        cost=0.25,
    )
    await seed_execution(
        bob,
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
        model="m1",
        task="chat",
        tokens_in=400,
        tokens_out=40,
        cost=1.0,
    )
    await seed_execution(
        bob, created_at=TO, model="m1", task="chat", tokens_in=999, tokens_out=999, cost=9.9
    )
    # Closed days are served from the rollup (usage spec §7) — roll them as
    # the nightly cron would, so the aggregates below see the seeded rows.
    await roll_days(FROM.date(), date(2026, 7, 20), date(2026, 7, 30), TO.date())
    return alice, bob


@pytest.mark.integration
async def test_summary_totals_and_breakdowns(
    client: AsyncClient, seeded: tuple[UUID, UUID]
) -> None:
    response = await client.get("/api/admin/usage/summary", params=PERIOD)
    assert response.status_code == 200
    payload = response.json()
    assert payload["tokens_in"] == 700
    assert payload["tokens_out"] == 70
    assert payload["total_cost"] == pytest.approx(1.75)
    assert payload["execution_count"] == 3
    by_model = {row["model"]: row for row in payload["by_model"]}
    assert by_model["m1"]["tokens_in"] == 500
    assert by_model["m1"]["execution_count"] == 2
    assert by_model["m2"]["total_cost"] == pytest.approx(0.25)
    assert payload["by_model"][0]["model"] == "m1"  # ordered by cost desc
    by_task = {row["task"]: row for row in payload["by_task"]}
    assert by_task["chat"]["tokens_in"] == 500
    assert by_task["summarize"]["execution_count"] == 1


@pytest.mark.integration
async def test_by_user_rows_with_usernames(client: AsyncClient, seeded: tuple[UUID, UUID]) -> None:
    alice, bob = seeded
    response = await client.get("/api/admin/usage/by-user", params=PERIOD)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    first = payload["items"][0]  # ordered by cost desc → bob first
    assert first["user_id"] == str(bob)
    assert first["username"] == "bob"
    assert first["total_cost"] == pytest.approx(1.0)
    second = payload["items"][1]
    assert second["user_id"] == str(alice)
    assert second["tokens_in"] == 300
    assert second["execution_count"] == 2


@pytest.mark.integration
async def test_by_user_pagination(client: AsyncClient, seeded: tuple[UUID, UUID]) -> None:
    response = await client.get(
        "/api/admin/usage/by-user", params={**PERIOD, "limit": 1, "offset": 0}
    )
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1


@pytest.mark.integration
async def test_recent_executions(client: AsyncClient, seeded: tuple[UUID, UUID]) -> None:
    response = await client.get("/api/admin/usage/executions", params=PERIOD)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    newest = payload["items"][0]
    assert newest["model"] == "m1"
    assert newest["tokens_in"] == 400
    assert newest["status"] == "ok"
    assert newest["username"] == "bob"


@pytest.mark.integration
async def test_recent_executions_filter_by_username(
    client: AsyncClient, seeded: tuple[UUID, UUID]
) -> None:
    response = await client.get("/api/admin/usage/executions", params={**PERIOD, "q": "ali"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert {row["username"] for row in payload["items"]} == {"alice"}


@pytest.mark.integration
async def test_recent_executions_filter_by_task(
    client: AsyncClient, seeded: tuple[UUID, UUID]
) -> None:
    response = await client.get(
        "/api/admin/usage/executions", params={**PERIOD, "task": "summarize"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["task"] == "summarize"
    assert payload["items"][0]["username"] == "alice"
