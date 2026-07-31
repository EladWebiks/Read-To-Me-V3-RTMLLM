"""Backoffice cross-user job listings (needs Postgres)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from app.modules.books.models import Book
from app.modules.downloads.models import DownloadJob
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from httpx import AsyncClient

from tests.admin.helpers import create_user, login, seed_session


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


async def seed_scrape_job(user_id: UUID, *, status: str = "pending") -> None:
    async with seed_session() as session:
        source = ScrapingSource(name=f"src-{uuid4().hex[:8]}", base_domains=["example.com"])
        session.add(source)
        await session.flush()
        session.add(
            ScrapingJob(
                user_id=user_id,
                source_id=source.id,
                start_url="https://example.com/book",
                status=status,
                message="Queued…",
            )
        )


async def seed_download_job(user_id: UUID, *, status: str = "pending") -> None:
    async with seed_session() as session:
        book = Book(title="Book", normalized_title="book")
        session.add(book)
        await session.flush()
        session.add(
            DownloadJob(
                user_id=user_id,
                book_id=book.id,
                chapter_from=1,
                chapter_to=3,
                provider="edge",
                voice="voice",
                status=status,
                total_count=3,
            )
        )


@pytest.mark.integration
async def test_scraping_jobs_cross_user(client: AsyncClient, admin: UUID) -> None:
    alice = await create_user("alice")
    bob = await create_user("bob")
    await seed_scrape_job(alice, status="running")
    await seed_scrape_job(bob, status="failed")
    response = await client.get("/api/admin/jobs/scraping")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    owners = {row["user_id"] for row in payload["items"]}
    assert owners == {str(alice), str(bob)}


@pytest.mark.integration
async def test_scraping_status_filter_and_paging(client: AsyncClient, admin: UUID) -> None:
    alice = await create_user("alice")
    await seed_scrape_job(alice, status="running")
    await seed_scrape_job(alice, status="failed")
    filtered = await client.get("/api/admin/jobs/scraping", params={"status": "failed"})
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["status"] == "failed"
    paged = await client.get("/api/admin/jobs/scraping", params={"limit": 1})
    assert paged.json()["total"] == 2
    assert len(paged.json()["items"]) == 1


@pytest.mark.integration
async def test_download_jobs_cross_user(client: AsyncClient, admin: UUID) -> None:
    alice = await create_user("alice")
    bob = await create_user("bob")
    await seed_download_job(alice, status="processing")
    await seed_download_job(bob, status="complete")
    response = await client.get("/api/admin/jobs/downloads")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    row = next(item for item in payload["items"] if item["user_id"] == str(alice))
    assert row["status"] == "processing"
    assert row["total_count"] == 3


@pytest.mark.integration
async def test_download_status_filter(client: AsyncClient, admin: UUID) -> None:
    alice = await create_user("alice")
    await seed_download_job(alice, status="processing")
    await seed_download_job(alice, status="complete")
    filtered = await client.get("/api/admin/jobs/downloads", params={"status": "complete"})
    assert filtered.json()["total"] == 1
