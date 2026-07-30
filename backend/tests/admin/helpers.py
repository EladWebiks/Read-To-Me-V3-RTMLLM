"""Seed/login helpers shared by backoffice API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from app.core.config import get_settings
from app.core.deps import COOKIE_NAME
from app.core.security import create_access_token
from app.modules.llm.models import LlmExecution
from app.modules.users.models import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# http.cookiejar drops cookies scoped to a single-label host (see test_auth_api.py).
HOST = "test.local"


@asynccontextmanager
async def seed_session() -> AsyncIterator[AsyncSession]:
    """Standalone committing session for seeding rows outside the app."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.commit()
    await engine.dispose()


async def create_user(
    username: str,
    *,
    is_admin: bool = False,
    deleted: bool = False,
) -> UUID:
    """Insert a user directly; returns its id."""
    async with seed_session() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=None,
            google_sub=f"{username}-sub",
            is_admin=is_admin,
            deleted_at=datetime.now(UTC) if deleted else None,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
    return user_id


async def seed_execution(  # noqa: PLR0913 — test seeding needs the full column set
    user_id: UUID,
    *,
    created_at: datetime,
    task: str = "chat",
    provider: str = "gemini",
    model: str = "gemini-3.5-flash",
    tokens_in: int = 100,
    tokens_out: int = 10,
    cost: float = 0.5,
) -> None:
    """Insert one llm_execution row with an explicit timestamp."""
    async with seed_session() as session:
        session.add(
            LlmExecution(
                user_id=user_id,
                task=task,
                provider=provider,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
                latency_ms=100,
                status="ok",
                created_at=created_at,
            )
        )


def login(client: AsyncClient, user_id: UUID, username: str) -> None:
    """Set a valid session cookie on the test client."""
    token = create_access_token(user_id=user_id, username=username, settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=HOST, path="/")
