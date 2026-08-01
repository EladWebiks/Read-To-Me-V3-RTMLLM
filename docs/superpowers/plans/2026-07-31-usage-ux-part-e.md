# End-User Usage UX (Part E) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give end users self-service quota visibility (`GET /api/me/usage` + a "Plan & usage" page reached from an avatar dropdown) and make the chat quota refusal durable and honest (persisted `quota_refusal` marker + a composer that locks with reset copy and survives reload).

**Architecture:** A self-serve router in `modules/usage/` (`router.py`) with composition logic in a new `self_service.py` — the second composition-layer file after `rollup.py` allowed to import domain services (spec §3.2 amendment; `read_service.py` stays pure, `usage` never imports orchestration). `used` per kind = Part D hybrid (rolled closed days + live today-tail from the owning domain's meter); `storage_bytes` is served live only. The chat refusal persists a `ConversationMessage(role="quota_refusal")` in the same commit as Part D's rejection row; the existing unknown-role filter in `_to_llm_messages` keeps it out of LLM context. The frontend adds a `features/usage/` feature (page + meters + format logic), a shared dropdown-menu wrapper for the avatar entry point, and a third composer-disable reason driven by both the live SSE error and the `['me', 'usage']` query.

**Tech Stack:** FastAPI, SQLAlchemy async, pydantic v2, React 19, react-query, Radix dropdown-menu, vitest.

**Spec:** `docs/superpowers/specs/2026-07-31-quota-usage-ux-design.md` (approved). Read §3.2–§3.4 before starting.

**Sequencing — PREREQUISITES ARE PLANS, NOT CODE (verified 2026-07-31: none of Parts A–D is implemented).** This plan starts only after **Part D Tasks 1–2 and 5 are merged** (which transitively requires all of Parts A–C). Task 1 Step 0 verifies this. Interfaces consumed here use the names the A–D plans define; if an A–D implementation diverged, reconcile to the merged names first and note the change.

## Global Constraints

- Backend gates per task (from `backend/`, **via the Bash tool** — `uv` is not on the PowerShell PATH): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`.
- Frontend gates (from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB — never the app DB.
- Commit per task: write the message to `/tmp/msg.txt`, then `bash scripts/git-commit-clean.sh /tmp/msg.txt`; verify with `git log -1 --format=%B`. **Never** add `Co-authored-by`/`Made-with` trailers.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. Frontend ESLint: file ≤110 lines, function ≤60 lines, nesting ≤3. Split helpers rather than disabling rules.
- Tests build settings via `tests/factories.py::make_settings` — never `Settings()` directly.
- Module direction: router → service → repository; services compose other modules' **services**, never their repositories. `usage/self_service.py` and `usage/rollup.py` are the only usage files that may import domain services; `usage` never imports orchestration.
- Frontend: server state via react-query; derive state during render — **never** a state setter inside `useEffect`; all fetching through `src/shared/lib/api.ts`.
- Semantics (spec, locked): admins are quota-exempt but still see their own `used`; `limit` null = unlimited; month window = UTC calendar month; `storage_bytes` is a live level meter with no reset; SSE/REST error contracts unchanged.

---

### Task 1: `GET /api/me/usage` (schemas, self-service composition, router, meter passthroughs)

**Files:**
- Create: `backend/app/modules/usage/schemas.py`
- Create: `backend/app/modules/usage/self_service.py`
- Create: `backend/app/modules/usage/router.py`
- Modify: `backend/app/main.py` (register router)
- Modify: `backend/app/modules/downloads/service.py` (meter passthroughs)
- Modify: `backend/app/modules/scraping/service.py` (meter passthrough)
- Modify: `backend/app/modules/imports/service.py` (meter passthrough)
- Test: `backend/tests/usage/test_me_usage_api.py`

**Interfaces:**
- Consumes (planned by Parts B–D; Step 0 verifies merged):
  - `QuotaService(session).limits_for(user: UserRead) -> QuotaLimits` (`.exempt`, `.limit(kind) -> float | None`), `QuotaService.current_month_window(now)` (Part B Task 1)
  - `QuotaKind`, `KIND_REGISTRY` (label/unit/window) (Part B Task 1)
  - `UsageReadService(session).rolled_month_amount(user_id, kind, now) -> float`, `UsageReadService.hybrid_split(now) -> tuple[date, datetime]` (Part D Task 1)
  - Domain repo meters (Part C Tasks 1–4): downloads `chapters_in_period(user_id, *, period_start, period_end) -> int`, `stored_bytes(user_id) -> int`; scraping `chapters_in_period(...) -> int`; imports `completed_in_period(...) -> int`
  - `LlmService(session, settings).usage_summary(user_id, *, period_start, period_end)` (existing; `.tokens_in`, `.tokens_out`, `.total_cost`)
  - `get_current_user` dep (`core/deps.py:26`)
- Produces (used by Tasks 3–6 and Part F):
  - `GET /api/me/usage` → `MeUsageResponse {membership: str, exempt: bool, as_of: datetime, resets_at: datetime, kinds: [MeUsageKindRead {kind, label, unit, window, used: float, limit: float | null}]}` — every `QuotaKind` present exactly once, registry order
  - `SelfUsageService(session, settings)` with `async usage_for(user: UserRead) -> MeUsageResponse`
  - Service passthroughs: `DownloadService.chapters_in_period(user_id, *, period_start, period_end) -> int`, `DownloadService.stored_bytes(user_id) -> int`, `ScrapingService.chapters_in_period(...) -> int`, `ImportService.completed_in_period(...) -> int`

- [ ] **Step 0: Verify prerequisites are merged (plans → code)**

```bash
uv run python -c "from app.modules.quotas.service import QuotaService; from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind; from app.modules.usage.read_service import UsageReadService; print('ok')"
grep -n "def chapters_in_period\|def stored_bytes" backend/app/modules/downloads/repository.py
grep -n "def chapters_in_period\|def chapters_this_month" backend/app/modules/scraping/repository.py
grep -n "def completed_in_period" backend/app/modules/imports/repository.py
```

Expected: `ok` plus one hit per meter. If a meter has a different merged name (e.g. scraping shipped `chapters_this_month`), use the merged name below and note it in the commit message. If the import fails, **STOP — Parts B–D are not merged; this plan cannot start.**

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/usage/test_me_usage_api.py
"""GET /api/me/usage: registry coverage, hybrid math, limits, admin (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.llm.models import LlmExecution
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import UsageFact, UsageMetric
from app.modules.usage.models import UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.membership import Membership
from app.modules.users.models import User
from datetime import UTC, datetime
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"
BASE = "/api/me/usage"


def _make_db_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _override_db


async def _clean(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        for model in (UsageDaily, MembershipQuota, LlmExecution):
            await session.execute(delete(model))
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _clean(session_factory)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    await _clean(session_factory)
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


async def _create_user(username: str, *, is_admin: bool = False) -> UUID:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=None,
            google_sub=f"{username}-sub",
            is_admin=is_admin,
        )
        session.add(user)
        await session.commit()
        user_id = user.id
    await engine.dispose()
    return user_id


def _login(client: AsyncClient, user_id: UUID, username: str) -> None:
    token = create_access_token(user_id=user_id, username=username, settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")


async def _seed_llm_usage(user_id: UUID, *, rolled: float, today_tokens: int) -> None:
    """A rolled closed-day row + a live llm_executions row for today."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        now = datetime.now(UTC)
        month_start, _ = QuotaService.current_month_window(now)
        if month_start.date() != now.date():  # skip rolled part on day 1 of month
            await UsageRepository(session).replace_day(
                month_start.date(),
                [UsageFact(user_id, UsageMetric.LLM_TOKENS_IN, rolled)],
            )
        session.add(
            LlmExecution(
                user_id=user_id,
                task="chat_tools",
                provider="gemini",
                model="m",
                tokens_in=today_tokens,
                tokens_out=0,
                cost=0.0,
                latency_ms=10,
                status="ok",
            )
        )
        session.add(
            MembershipQuota(
                membership=Membership.FREE.value,
                quota_kind=QuotaKind.LLM_TOKENS.value,
                limit_value=5000.0,
            )
        )
        await session.commit()
    await engine.dispose()


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


@pytest.mark.integration
async def test_every_kind_present_with_hybrid_usage_and_limits(client: AsyncClient) -> None:
    user_id = await _create_user("me-usage-reader")
    rolled = 100.0
    now = datetime.now(UTC)
    on_day_one = QuotaService.current_month_window(now)[0].date() == now.date()
    await _seed_llm_usage(user_id, rolled=rolled, today_tokens=40)
    _login(client, user_id, "me-usage-reader")

    response = await client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["membership"] == "free"
    assert body["exempt"] is False
    assert body["resets_at"].startswith(
        QuotaService.current_month_window(now)[1].date().isoformat()
    )
    kinds = {k["kind"]: k for k in body["kinds"]}
    assert set(kinds) == {k.value for k in QuotaKind}  # registry-driven, all present

    llm = kinds["llm_tokens"]
    expected = 40.0 if on_day_one else rolled + 40.0  # rolled closed day + live today
    assert llm["used"] == expected
    assert llm["limit"] == 5000.0
    assert llm["window"] == "month"
    assert kinds["llm_cost_usd"]["limit"] is None  # no rule = unlimited
    storage = kinds["storage_bytes"]
    assert storage["window"] == "standing"
    assert storage["used"] == 0.0  # no download jobs seeded: live meter reads zero


@pytest.mark.integration
async def test_admin_is_exempt_but_sees_usage(client: AsyncClient) -> None:
    user_id = await _create_user("me-usage-admin", is_admin=True)
    await _seed_llm_usage(user_id, rolled=100.0, today_tokens=40)
    _login(client, user_id, "me-usage-admin")

    body = (await client.get(BASE)).json()
    assert body["exempt"] is True
    kinds = {k["kind"]: k for k in body["kinds"]}
    assert kinds["llm_tokens"]["limit"] is None  # exempt: every limit null
    assert kinds["llm_tokens"]["used"] > 0  # usage still computed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/usage/test_me_usage_api.py -v`
Expected: FAIL — 404 (route missing).

- [ ] **Step 3: Add the domain service meter passthroughs**

One-line pass-throughs so the composition layer talks to **services**, never foreign repositories. In `backend/app/modules/downloads/service.py` (inside `DownloadService`; import `datetime` if missing):

```python
    async def chapters_in_period(
        self, user_id: UUID, *, period_start: datetime, period_end: datetime
    ) -> int:
        """Month audio-chapter meter (soft-deleted included) for usage composition."""
        return await self._repo.chapters_in_period(
            user_id, period_start=period_start, period_end=period_end
        )

    async def stored_bytes(self, user_id: UUID) -> int:
        """Live retained-MP3 bytes (level meter) for usage composition."""
        return await self._repo.stored_bytes(user_id)
```

In `backend/app/modules/scraping/service.py` (`ScrapingService`) and `backend/app/modules/imports/service.py` (`ImportService`), the same shape over their Part C meters:

```python
    async def chapters_in_period(
        self, user_id: UUID, *, period_start: datetime, period_end: datetime
    ) -> int:
        """Month scraped-chapter meter for usage composition."""
        return await self._repo.chapters_in_period(
            user_id, period_start=period_start, period_end=period_end
        )
```

```python
    async def completed_in_period(
        self, user_id: UUID, *, period_start: datetime, period_end: datetime
    ) -> int:
        """Month completed-EPUB-imports meter for usage composition."""
        return await self._repo.completed_in_period(
            user_id, period_start=period_start, period_end=period_end
        )
```

If a Part C meter merged under a different name/holder (Step 0), delegate to the merged name — the **service method names above are the contract** later steps use.

- [ ] **Step 4: Schemas**

```python
# backend/app/modules/usage/schemas.py
"""Pydantic DTOs for the self-serve usage endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.modules.quotas.kinds import QuotaKind


class MeUsageKindRead(BaseModel):
    """One quota kind with hybrid usage and the caller's resolved limit."""

    kind: QuotaKind
    label: str
    unit: str
    window: Literal["month", "standing"]
    used: float
    limit: float | None  # None = unlimited (row absent or exempt)


class MeUsageResponse(BaseModel):
    membership: str
    exempt: bool  # admins: limits all None but usage still shown
    as_of: datetime
    resets_at: datetime  # month-window end; standing kinds ignore it
    kinds: list[MeUsageKindRead]
```

- [ ] **Step 5: Self-service composition**

```python
# backend/app/modules/usage/self_service.py
"""Self-serve usage composition.

COMPOSITION LAYER: with rollup.py, one of exactly two usage files allowed to
import domain services (spec 2026-07-31-quota-usage-ux §3.2 amendment).
read_service.py stays pure so domain services can import it cycle-free.
usage never imports orchestration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.downloads.service import DownloadService
from app.modules.imports.service import ImportService
from app.modules.llm.service import LlmService
from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.scraping.service import ScrapingService
from app.modules.usage.read_service import UsageReadService
from app.modules.usage.schemas import MeUsageKindRead, MeUsageResponse
from app.modules.users.schemas import UserRead


class SelfUsageService:
    """Compose per-kind hybrid usage + resolved limits for one user."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._llm = LlmService(session, settings)
        self._reads = UsageReadService(session)

    async def usage_for(self, user: UserRead) -> MeUsageResponse:
        now = datetime.now(UTC)
        _, month_end = QuotaService.current_month_window(now)
        _, today_start = UsageReadService.hybrid_split(now)
        limits = await QuotaService(self._session).limits_for(user)
        kinds = [
            MeUsageKindRead(
                kind=kind,
                label=meta.label,
                unit=meta.unit,
                window=meta.window,
                used=await self._used(kind, user.id, now, today_start, month_end),
                limit=limits.limit(kind),
            )
            for kind, meta in KIND_REGISTRY.items()
        ]
        return MeUsageResponse(
            membership=user.membership.value,
            exempt=limits.exempt,
            as_of=now,
            resets_at=month_end,
            kinds=kinds,
        )

    async def _used(
        self, kind: QuotaKind, user_id: UUID, now: datetime, start: datetime, end: datetime
    ) -> float:
        """Hybrid month amount, or the live level for storage (never rolled)."""
        if kind is QuotaKind.STORAGE_BYTES:
            return float(await DownloadService(self._session).stored_bytes(user_id))
        rolled = await self._reads.rolled_month_amount(user_id, kind, now)
        return rolled + await self._today_tail(kind, user_id, start, end)

    async def _today_tail(
        self, kind: QuotaKind, user_id: UUID, start: datetime, end: datetime
    ) -> float:
        # Two LLM kinds -> two usage_summary calls; both are single index
        # scans over one day (documented, acceptable at this scale).
        if kind in (QuotaKind.LLM_TOKENS, QuotaKind.LLM_COST_USD):
            summary = await self._llm.usage_summary(user_id, period_start=start, period_end=end)
            if kind is QuotaKind.LLM_TOKENS:
                return float(summary.tokens_in + summary.tokens_out)
            return float(summary.total_cost)
        if kind is QuotaKind.AUDIO_CHAPTERS:
            svc = DownloadService(self._session)
            return float(await svc.chapters_in_period(user_id, period_start=start, period_end=end))
        if kind is QuotaKind.SCRAPE_CHAPTERS:
            svc = ScrapingService(self._session)
            return float(await svc.chapters_in_period(user_id, period_start=start, period_end=end))
        svc = ImportService(self._session)
        return float(await svc.completed_in_period(user_id, period_start=start, period_end=end))
```

(If the merged `ImportService`/`ScrapingService` constructors take extra args — check how their routers build them — construct them the same way here.)

- [ ] **Step 6: Router + registration**

```python
# backend/app/modules/usage/router.py
"""Self-serve usage endpoint. Identity comes from the session cookie ONLY."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_current_user, get_db, get_settings
from app.modules.usage.schemas import MeUsageResponse
from app.modules.usage.self_service import SelfUsageService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/me", tags=["usage"])


@router.get("/usage")
async def my_usage(
    user: Annotated[UserRead, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeUsageResponse:
    """Tier + per-kind hybrid usage vs limits for the authenticated user."""
    return await SelfUsageService(session, settings).usage_for(user)
```

(`get_settings` here must be whatever dependency the existing routers use for effective settings — mirror `admin/usage_router.py`'s import exactly.) In `backend/app/main.py`: `from app.modules.usage.router import router as usage_router` and `app.include_router(usage_router, prefix=api_prefix)` next to the other routers.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/usage/test_me_usage_api.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add self-serve GET /api/me/usage with hybrid per-kind usage\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Persist the chat quota refusal marker

**Files:**
- Modify: `backend/app/modules/orchestration/service.py` (quota catch in `run` + helper)
- Test: `backend/tests/orchestration/test_quota_refusal_marker.py`

**Interfaces:**
- Consumes: the quota catch Part B Task 3 added to `OrchestrationService.run` (`except QuotaExceededError: yield _quota_error_event(exc); return`), which Part D Task 2 extended to record the rejection and commit; `self._repo.add_message(conversation_id, *, role, content)` (`llm/repository.py:475`); `_to_llm_messages` unknown-role filter (`orchestration/service.py:636-643`).
- Produces: module constant `QUOTA_REFUSAL_ROLE = "quota_refusal"`; a `ConversationMessage` row with that role and `content == str(exc)` persisted in the same commit as the rejection row. Task 6's frontend renders this role; hydration (`GET /api/chat/{id}`) serves it with no backend changes (`role` is a plain string end-to-end).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/orchestration/test_quota_refusal_marker.py
"""Quota refusals persist a marker message; context building excludes it (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import ConversationMessage, LlmExecution
from app.modules.llm.types import ToolCallingRequest, ToolCallingResponse, Usage
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.orchestration.service import QUOTA_REFUSAL_ROLE, _to_llm_messages
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        for model in (MembershipQuota, MembershipPolicy, LlmExecution):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
        for model in (MembershipQuota, MembershipPolicy, LlmExecution):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


def _settings() -> Settings:
    return make_settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
    )


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"ref_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _block_user(session: AsyncSession, user_id: UUID) -> None:
    """Tiny token quota + existing usage puts the user at/over the cap."""
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.LLM_TOKENS.value,
            limit_value=10.0,
        )
    )
    session.add(
        LlmExecution(
            user_id=user_id,
            task="chat_tools",
            provider="gemini",
            model="m",
            tokens_in=10,
            tokens_out=5,
            cost=0.0,
            latency_ms=10,
            status="ok",
        )
    )
    await session.commit()


def _never_llm() -> Any:
    async def _fake(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        raise AssertionError("provider must not be called")

    return _fake


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refusal_persists_marker_matching_sse_detail(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(session)
    await _block_user(session, user.id)
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_never_llm()))

    events = [e async for e in service.stream_chat(user, "hello", None)]
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "quota_exceeded"
    conv_id = UUID(str(events[0].data["conversation_id"]))

    rows = (
        await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv_id)
            .order_by(ConversationMessage.created_at)
        )
    ).scalars().all()
    roles = [row.role for row in rows]
    assert roles == ["user", QUOTA_REFUSAL_ROLE]  # orphan explained, nothing else
    assert rows[-1].content == error.data["detail"]  # same user copy as the SSE event


@pytest.mark.unit
def test_context_builder_excludes_quota_refusal_rows() -> None:
    """The unknown-role filter (service.py Role(row.role) -> ValueError -> skip)
    must keep refusal copy out of LLM prompts. This test pins that contract."""
    rows = [
        ConversationMessage(
            conversation_id=uuid4(),
            role=role,
            content=content,
            created_at=datetime.now(UTC),
        )
        for role, content in (
            ("user", "hi"),
            (QUOTA_REFUSAL_ROLE, "Monthly AI tokens quota reached (15/10 tokens)."),
            ("assistant", "hello"),
        )
    ]
    contents = [m.content for m in _to_llm_messages(rows)]
    assert "hi" in contents
    assert "hello" in contents
    assert not any("quota" in c for c in contents)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/orchestration/test_quota_refusal_marker.py -v`
Expected: FAIL — `ImportError: cannot import name 'QUOTA_REFUSAL_ROLE'`.

- [ ] **Step 3: Persist the marker in the quota catch**

In `backend/app/modules/orchestration/service.py`, add a module-level constant near the top:

```python
# Persisted role for quota refusals. NOT a member of llm.types.Role on
# purpose: _to_llm_messages drops roles Role() cannot parse, which is what
# keeps refusal copy out of future prompts (spec §3.3). If Role ever grows
# this value, add an explicit skip there.
QUOTA_REFUSAL_ROLE = "quota_refusal"
```

Extend the quota catch in `run` (the block Part D Task 2 already made record the rejection; keep its rejection insert + commit and add the marker to the same commit — one commit covers both rows):

```python
        try:
            await self._check_llm_quota(user)
        except QuotaExceededError as exc:
            # Same-session write: rejection row (Part D) + refusal marker, one
            # commit, then the SSE error. The user's message is already
            # persisted; the marker is what explains it after a reload.
            await self._repo.add_message(
                conversation_id, role=QUOTA_REFUSAL_ROLE, content=str(exc)
            )
            await self._reads.record_rejection(user.id, exc.kind, "chat")
            await self._session.commit()
            yield _quota_error_event(exc)
            return
```

Reconcile with the merged Part D Task 2 code: if D2 shipped a helper (e.g. `self._record_rejection(...)`) call it instead of the inline `record_rejection` line — the invariant is **marker + rejection in one commit, then the SSE event**. Do not change `_quota_error_event` (locked SSE shape).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/orchestration/test_quota_refusal_marker.py tests/orchestration/test_monthly_quota_enforcement.py -v`
Expected: PASS (new tests + Part B's enforcement suite unchanged).

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: persist quota_refusal marker message on chat quota rejection\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: Frontend usage feature foundation (API client, hook, format logic)

**Files:**
- Create: `frontend/src/features/usage/api/meUsage.ts`
- Create: `frontend/src/features/usage/hooks/useMeUsage.ts`
- Create: `frontend/src/features/usage/logic/format.ts`
- Create: `frontend/src/features/usage/logic/format.test.ts`
- Create: `frontend/src/features/usage/index.ts` (barrel; starts empty-ish, Task 4 fills it)

**Interfaces:**
- Consumes: `GET /api/me/usage` (Task 1), `apiGet` from `@/shared/lib/api`.
- Produces (used by Tasks 4–6):
  - Types `MeUsageKind {kind: string; label: string; unit: string; window: 'month' | 'standing'; used: number; limit: number | null}` and `MeUsage {membership: string; exempt: boolean; as_of: string; resets_at: string; kinds: MeUsageKind[]}`
  - `fetchMeUsage(): Promise<MeUsage>`; `meUsageKey = ['me', 'usage'] as const`; `useMeUsage()` (react-query, staleTime 30s)
  - `meterState(used, limit) -> 'unlimited' | 'ok' | 'warn' | 'over'` (warn at ≥80%, over at ≥100%), `meterPercent(used, limit) -> number` (0–100, clamped), `formatAmount(value, unit) -> string` (bytes → MB/GB, USD → `$x.xx`, else thousands-separated), `resetLabel(resetsAt) -> string`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/features/usage/logic/format.test.ts
import { describe, expect, it } from 'vitest'
import { formatAmount, meterPercent, meterState, resetLabel } from './format'

describe('meterState', () => {
  it('is unlimited when limit is null', () => {
    expect(meterState(999, null)).toBe('unlimited')
  })
  it('is ok under 80%, warn from 80%, over from 100%', () => {
    expect(meterState(79, 100)).toBe('ok')
    expect(meterState(80, 100)).toBe('warn')
    expect(meterState(99, 100)).toBe('warn')
    expect(meterState(100, 100)).toBe('over')
    expect(meterState(150, 100)).toBe('over')
  })
})

describe('meterPercent', () => {
  it('clamps to 0..100 and handles null limit', () => {
    expect(meterPercent(50, 100)).toBe(50)
    expect(meterPercent(150, 100)).toBe(100)
    expect(meterPercent(10, null)).toBe(0)
  })
})

describe('formatAmount', () => {
  it('formats bytes as MB/GB', () => {
    expect(formatAmount(52428800, 'bytes')).toBe('50.0 MB')
    expect(formatAmount(2147483648, 'bytes')).toBe('2.0 GB')
  })
  it('formats USD with two decimals and tokens with separators', () => {
    expect(formatAmount(1.5, 'USD')).toBe('$1.50')
    expect(formatAmount(1234567, 'tokens')).toBe('1,234,567')
  })
})

describe('resetLabel', () => {
  it('renders a readable date and falls back gracefully', () => {
    expect(resetLabel('2026-08-01T00:00:00+00:00')).toContain('2026')
    expect(resetLabel('not-a-date')).toBe('next month')
  })
})
```

Run (from `frontend/`): `npm run test -- format` — expected FAIL (module not found).

- [ ] **Step 2: Implement `format.ts`**

```typescript
// frontend/src/features/usage/logic/format.ts
/** Meter math + unit formatting for usage displays (spec §3.4). */

export type MeterState = 'unlimited' | 'ok' | 'warn' | 'over'

export function meterState(used: number, limit: number | null): MeterState {
  if (limit === null || limit <= 0) return 'unlimited'
  const ratio = used / limit
  if (ratio >= 1) return 'over'
  if (ratio >= 0.8) return 'warn'
  return 'ok'
}

export function meterPercent(used: number, limit: number | null): number {
  if (limit === null || limit <= 0) return 0
  return Math.min(100, Math.max(0, (used / limit) * 100))
}

export function formatAmount(value: number, unit: string): string {
  if (unit === 'bytes') return formatBytes(value)
  if (unit === 'USD') return `$${value.toFixed(2)}`
  return Math.round(value).toLocaleString('en-US')
}

function formatBytes(value: number): string {
  const gb = value / 1024 ** 3
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  return `${(value / 1024 ** 2).toFixed(1)} MB`
}

export function resetLabel(resetsAt: string): string {
  const date = new Date(resetsAt)
  if (Number.isNaN(date.getTime())) return 'next month'
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}
```

Run: `npm run test -- format` — expected PASS.

- [ ] **Step 3: API client + hook**

```typescript
// frontend/src/features/usage/api/meUsage.ts
import { apiGet } from '@/shared/lib/api'

/** Mirrors usage/schemas.py::MeUsageResponse. */
export type MeUsageKind = {
  kind: string
  label: string
  unit: string
  window: 'month' | 'standing'
  used: number
  limit: number | null
}

export type MeUsage = {
  membership: string
  exempt: boolean
  as_of: string
  resets_at: string
  kinds: MeUsageKind[]
}

export function fetchMeUsage(): Promise<MeUsage> {
  return apiGet('/api/me/usage')
}
```

```typescript
// frontend/src/features/usage/hooks/useMeUsage.ts
import { useQuery } from '@tanstack/react-query'
import { fetchMeUsage } from '../api/meUsage'

export const meUsageKey = ['me', 'usage'] as const

export function useMeUsage() {
  return useQuery({ queryKey: meUsageKey, queryFn: fetchMeUsage, staleTime: 30_000 })
}
```

```typescript
// frontend/src/features/usage/index.ts
export { useMeUsage, meUsageKey } from './hooks/useMeUsage'
export { formatAmount, meterPercent, meterState, resetLabel } from './logic/format'
export type { MeUsage, MeUsageKind } from './api/meUsage'
```

- [ ] **Step 4: Frontend gates + commit**

```bash
npm run test
npm run lint
npm run build
printf 'feat: add usage feature foundation (me-usage client, hook, meter logic)\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: "Plan & usage" page + route

**Files:**
- Create: `frontend/src/features/usage/components/MeterRow.tsx`
- Create: `frontend/src/features/usage/components/StorageSection.tsx`
- Create: `frontend/src/features/usage/components/UsagePage.tsx`
- Create: `frontend/src/features/usage/components/UsagePage.test.tsx`
- Modify: `frontend/src/features/usage/index.ts` (export `UsagePage`)
- Modify: `frontend/src/app/App.tsx` (route `/usage` inside the protected shell)

**Interfaces:**
- Consumes: `useMeUsage`, `MeUsageKind`, `meterState`/`meterPercent`/`formatAmount`/`resetLabel` (Task 3).
- Produces: `UsagePage` component at route `/usage` (protected, not admin-gated). Task 5 links to this route.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/usage/components/UsagePage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { MeUsage } from '../api/meUsage'
import { UsagePage } from './UsagePage'

const usage: MeUsage = {
  membership: 'free',
  exempt: false,
  as_of: '2026-07-31T12:00:00+00:00',
  resets_at: '2026-08-01T00:00:00+00:00',
  kinds: [
    { kind: 'llm_tokens', label: 'AI tokens', unit: 'tokens', window: 'month', used: 4500, limit: 5000 },
    { kind: 'llm_cost_usd', label: 'AI spend', unit: 'USD', window: 'month', used: 0.5, limit: null },
    { kind: 'storage_bytes', label: 'Download storage', unit: 'bytes', window: 'standing', used: 52428800, limit: null },
  ],
}

vi.mock('../api/meUsage', () => ({ fetchMeUsage: vi.fn(async () => usage) }))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <UsagePage />
    </QueryClientProvider>,
  )
}

describe('UsagePage', () => {
  it('renders tier, reset date, month meters, and the storage section', async () => {
    renderPage()
    expect(await screen.findByText(/free/i)).toBeInTheDocument()
    expect(screen.getByText(/AI tokens/)).toBeInTheDocument()
    expect(screen.getByText('4,500 / 5,000')).toBeInTheDocument()
    expect(screen.getByText(/Unlimited/)).toBeInTheDocument() // llm_cost_usd, no bar
    expect(screen.getByText(/50\.0 MB/)).toBeInTheDocument() // storage section
    expect(screen.getByText(/Frees up when downloads expire/)).toBeInTheDocument()
  })

  it('marks a ≥80% meter as warning', async () => {
    renderPage()
    const meter = await screen.findByRole('progressbar', { name: /AI tokens/ })
    expect(meter).toHaveAttribute('data-state', 'warn') // 4500/5000 = 90%
  })
})
```

Run: `npm run test -- UsagePage` — expected FAIL (module not found).

- [ ] **Step 2: Implement `MeterRow`**

```tsx
// frontend/src/features/usage/components/MeterRow.tsx
import type { MeUsageKind } from '../api/meUsage'
import { formatAmount, meterPercent, meterState } from '../logic/format'

const BAR_COLOR: Record<string, string> = {
  ok: 'bg-primary',
  warn: 'bg-amber-500',
  over: 'bg-destructive',
}

/** One month-kind meter: label, used/limit, threshold-colored bar. */
export function MeterRow({ kind }: { kind: MeUsageKind }) {
  const state = meterState(kind.used, kind.limit)
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{kind.label}</span>
        <span className="text-muted-foreground">
          {state === 'unlimited'
            ? `${formatAmount(kind.used, kind.unit)} · Unlimited`
            : `${formatAmount(kind.used, kind.unit)} / ${formatAmount(kind.limit ?? 0, kind.unit)}`}
        </span>
      </div>
      {state !== 'unlimited' && (
        <div
          role="progressbar"
          aria-label={kind.label}
          aria-valuenow={Math.round(meterPercent(kind.used, kind.limit))}
          aria-valuemin={0}
          aria-valuemax={100}
          data-state={state}
          className="h-1.5 overflow-hidden rounded-full bg-muted"
        >
          <div
            className={`h-full rounded-full transition-all ${BAR_COLOR[state]}`}
            style={{ width: `${meterPercent(kind.used, kind.limit)}%` }}
          />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Implement `StorageSection` and `UsagePage`**

```tsx
// frontend/src/features/usage/components/StorageSection.tsx
import type { MeUsageKind } from '../api/meUsage'
import { MeterRow } from './MeterRow'

/** Standing (level) meters — no monthly reset; freed assets stop counting. */
export function StorageSection({ kinds }: { kinds: MeUsageKind[] }) {
  if (kinds.length === 0) return null
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold">Storage</h2>
      {kinds.map((kind) => (
        <MeterRow key={kind.kind} kind={kind} />
      ))}
      <p className="text-xs text-muted-foreground">
        Frees up when downloads expire or are deleted.
      </p>
    </section>
  )
}
```

```tsx
// frontend/src/features/usage/components/UsagePage.tsx
import { useMeUsage } from '../hooks/useMeUsage'
import { resetLabel } from '../logic/format'
import { MeterRow } from './MeterRow'
import { StorageSection } from './StorageSection'

export function UsagePage() {
  const { data, isPending, isError } = useMeUsage()
  if (isPending) return <p className="p-6 text-sm text-muted-foreground">Loading usage…</p>
  if (isError || !data)
    return <p className="p-6 text-sm text-destructive">Could not load usage.</p>
  const monthly = data.kinds.filter((k) => k.window === 'month')
  const standing = data.kinds.filter((k) => k.window === 'standing')
  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold">Plan &amp; usage</h1>
        <p className="text-sm text-muted-foreground">
          <span className="capitalize">{data.membership}</span> plan · Usage resets{' '}
          {resetLabel(data.resets_at)}
        </p>
        {data.exempt && (
          <p className="text-xs text-muted-foreground">No limits apply (admin).</p>
        )}
      </header>
      <section className="space-y-3">
        <h2 className="text-sm font-semibold">This month</h2>
        {monthly.map((kind) => (
          <MeterRow key={kind.kind} kind={kind} />
        ))}
      </section>
      <StorageSection kinds={standing} />
    </div>
  )
}
```

Add to `frontend/src/features/usage/index.ts`: `export { UsagePage } from './components/UsagePage'`.

- [ ] **Step 4: Route**

In `frontend/src/app/App.tsx`: import `{ UsagePage } from '@/features/usage'` and add, next to the other protected (non-admin) routes:

```tsx
<Route path="/usage" element={<UsagePage />} />
```

Place it inside the same protected-shell route group as `/library` (NOT under `RequireAdmin`).

- [ ] **Step 5: Run tests, gates, commit**

```bash
npm run test
npm run lint
npm run build
printf 'feat: add Plan & usage page with threshold meters\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Avatar dropdown entry point

**Files:**
- Create: `frontend/src/shared/ui/dropdown-menu.tsx`
- Modify: `frontend/src/shared/ui/index.ts` (export)
- Modify: `frontend/src/layout/UserAvatar.tsx` (tooltip avatar → dropdown trigger)
- Modify: `frontend/src/layout/UserAvatar.test.tsx` (existing test file)

**Interfaces:**
- Consumes: `@radix-ui/react-dropdown-menu` (already in `package.json`, unwrapped); the `useMe()` user (`membership`, `email`) already passed into `UserAvatar` from `ShellActions.tsx:30`; route `/usage` (Task 4).
- Produces: `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuLabel`, `DropdownMenuSeparator` in `shared/ui`; `UserAvatar` opens a menu with email, tier, and a "Plan & usage" link.

- [ ] **Step 1: Wrap the Radix dropdown**

Follow the wrapper style of `shared/ui/tooltip.tsx` (thin re-exports + styled Content):

```tsx
// frontend/src/shared/ui/dropdown-menu.tsx
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '@/shared/lib/utils'

export const DropdownMenu = DropdownMenuPrimitive.Root
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
export const DropdownMenuLabel = DropdownMenuPrimitive.Label
export const DropdownMenuSeparator = DropdownMenuPrimitive.Separator

export function DropdownMenuContent({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        sideOffset={6}
        className={cn(
          'z-50 min-w-44 rounded-xl border bg-popover p-1.5 text-sm text-popover-foreground shadow-md',
          className,
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  )
}

export function DropdownMenuItem({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item>) {
  return (
    <DropdownMenuPrimitive.Item
      className={cn(
        'cursor-pointer rounded-lg px-2.5 py-1.5 outline-none focus:bg-accent focus:text-accent-foreground',
        className,
      )}
      {...props}
    />
  )
}
```

(If `shared/lib/utils.ts` has no `cn`, use the same class-merge helper `tooltip.tsx` uses — mirror it exactly.) Export all six from `shared/ui/index.ts`.

- [ ] **Step 2: Rework `UserAvatar`**

Replace the `IconTooltip` wrapper with a dropdown (keep the avatar circle exactly as rendered today; the tooltip goes away — email moves into the menu):

```tsx
// frontend/src/layout/UserAvatar.tsx  (shape — keep the existing avatar markup)
import { useNavigate } from 'react-router-dom'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui'

export function UserAvatar({ user }: { user: { email?: string | null; membership: string } }) {
  const navigate = useNavigate()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account menu" className="rounded-full outline-none">
        {/* existing 7x7 avatar circle markup, unchanged */}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="px-2.5 py-1.5 text-xs text-muted-foreground">
          {user.email ?? 'Signed in'}
          <span className="block capitalize">{user.membership} plan</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="my-1 h-px bg-border" />
        <DropdownMenuItem onSelect={() => navigate('/usage')}>Plan &amp; usage</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

Adapt the props to whatever `UserAvatar` receives today (`ShellActions.tsx:30` passes `data.user`; keep its type). Logout stays where it is.

- [ ] **Step 3: Update the test**

In `frontend/src/layout/UserAvatar.test.tsx`, adjust existing assertions that referenced the tooltip email (the email now appears inside the opened menu) and add:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

it('opens a menu with Plan & usage and navigates to /usage', async () => {
  render(
    <MemoryRouter initialEntries={['/library']}>
      <Routes>
        <Route
          path="/library"
          element={<UserAvatar user={{ email: 'a@b.c', membership: 'free' }} />}
        />
        <Route path="/usage" element={<div>usage-page-marker</div>} />
      </Routes>
    </MemoryRouter>,
  )
  fireEvent.click(screen.getByLabelText('Account menu'))
  expect(await screen.findByText('a@b.c')).toBeInTheDocument()
  fireEvent.click(screen.getByText('Plan & usage'))
  expect(await screen.findByText('usage-page-marker')).toBeInTheDocument()
})
```

(Adapt the `user` prop to `UserAvatar`'s actual prop type; wrap in the app's `TooltipProvider`/theme providers only if the existing test file already does.)

- [ ] **Step 4: Gates + commit**

```bash
npm run test
npm run lint
npm run build
printf 'feat: avatar dropdown with Plan & usage entry\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Chat quota UX (refusal rendering + informed composer lock)

**Files:**
- Modify: `frontend/src/features/assistant/api/chatTypes.ts` (`ChatRole` + `quota_refusal`)
- Create: `frontend/src/features/assistant/logic/quotaState.ts`
- Create: `frontend/src/features/assistant/logic/quotaState.test.ts`
- Modify: `frontend/src/features/assistant/hooks/streamHandlers.ts` (quota branch in `onError`)
- Modify: `frontend/src/features/assistant/hooks/useAssistantChat.ts` (quota block state, expose)
- Modify: `frontend/src/features/assistant/components/chatTurnParts.tsx` (`QuotaRefusalNote`)
- Modify: `frontend/src/features/assistant/components/ChatTurn.tsx` (role branch + unknown-role fallback)
- Modify: `frontend/src/features/assistant/components/AssistantComposer.tsx` (third disable reason)
- Modify: `frontend/src/features/assistant/components/AssistantChat.tsx` (wire the prop)

**Interfaces:**
- Consumes: SSE `onError(detail, code, resetsAt)` threading (Part B Task 4), `chatErrorMessage` (`logic/errorCopy.ts`, Part B Task 4), `useMeUsage`/`MeUsage` + `resetLabel` (Tasks 3–4), persisted `quota_refusal` rows served by hydration (Task 2), `composerPlaceholder` (`AssistantComposer.tsx:100-108`) and `disabled = sending || blocked` (`:25`).
- Produces: `quotaLock(usage: MeUsage | undefined, sseResetsAt: string | null) -> string | null` (returns the composer notice or null); `AssistantComposer` prop `quotaNotice?: string | null`; `ChatTurn` renders `quota_refusal` (and unknown roles) as a muted amber note.

- [ ] **Step 1: Write the failing logic tests**

```typescript
// frontend/src/features/assistant/logic/quotaState.test.ts
import { describe, expect, it } from 'vitest'
import type { MeUsage } from '@/features/usage'
import { quotaLock } from './quotaState'

function usage(overrides: Partial<MeUsage['kinds'][number]>[]): MeUsage {
  return {
    membership: 'free',
    exempt: false,
    as_of: '',
    resets_at: '2026-08-01T00:00:00+00:00',
    kinds: overrides.map((o) => ({
      kind: 'llm_tokens',
      label: 'AI tokens',
      unit: 'tokens',
      window: 'month' as const,
      used: 0,
      limit: null,
      ...o,
    })),
  }
}

describe('quotaLock', () => {
  it('locks from a live SSE resets_at regardless of query state', () => {
    expect(quotaLock(undefined, '2026-08-01T00:00:00+00:00')).toContain('resets')
  })
  it('locks when an LLM kind is at/over its limit', () => {
    const lock = quotaLock(usage([{ kind: 'llm_tokens', used: 100, limit: 100 }]), null)
    expect(lock).toContain('Monthly AI limit reached')
  })
  it('stays open under the limit, for unlimited kinds, for exempt users, and for non-LLM kinds', () => {
    expect(quotaLock(usage([{ used: 99, limit: 100 }]), null)).toBeNull()
    expect(quotaLock(usage([{ used: 100, limit: null }]), null)).toBeNull()
    const exempt = { ...usage([{ used: 100, limit: 100 }]), exempt: true }
    expect(quotaLock(exempt, null)).toBeNull()
    expect(
      quotaLock(usage([{ kind: 'audio_chapters', used: 100, limit: 100 }]), null),
    ).toBeNull()
  })
})
```

Run: `npm run test -- quotaState` — expected FAIL (module not found).

- [ ] **Step 2: Implement `quotaState.ts`**

```typescript
// frontend/src/features/assistant/logic/quotaState.ts
/** Composer quota lock, derived DURING RENDER (never set in an effect).

Two sources (spec §3.3): a live quota_exceeded SSE error (resets_at captured
in session state) and the ['me','usage'] query — so the lock survives reload
and releases when a raised quota shows up on the next query refresh. */
import { resetLabel, type MeUsage } from '@/features/usage'

const LLM_KINDS = new Set(['llm_tokens', 'llm_cost_usd'])

export function quotaLock(usage: MeUsage | undefined, sseResetsAt: string | null): string | null {
  const resetsAt = sseResetsAt ?? usageBlockedResetsAt(usage)
  if (resetsAt === null) return null
  return `Monthly AI limit reached — resets ${resetLabel(resetsAt)}`
}

function usageBlockedResetsAt(usage: MeUsage | undefined): string | null {
  if (!usage || usage.exempt) return null
  const blocked = usage.kinds.some(
    (k) => LLM_KINDS.has(k.kind) && k.limit !== null && k.used >= k.limit,
  )
  return blocked ? usage.resets_at : null
}
```

Run: `npm run test -- quotaState` — expected PASS.

- [ ] **Step 3: Role type, note rendering**

In `chatTypes.ts`, extend the union: `ChatRole = ... | 'cancelled' | 'quota_refusal'`.

In `chatTurnParts.tsx`, next to `CancelledNote`:

```tsx
export function QuotaRefusalNote({ content }: { content: string }) {
  return (
    <p className="rounded-xl bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
      {content}
    </p>
  )
}
```

In `ChatTurn.tsx`: add the `quota_refusal` branch rendering `<QuotaRefusalNote content={message.content} />`, and make the **final fallback** (roles the switch doesn't know) render the same muted note instead of nothing — future persisted roles must degrade visibly, not vanish.

- [ ] **Step 4: Stream handler + state + composer**

In `useAssistantChat.ts`: add `const [quotaResetsAt, setQuotaResetsAt] = useState<string | null>(null)`; clear it at the start of a successful send only if you already cleared errors there (mirror the existing `setError(null)` site in `chatActionStreams.ts:29`); expose `quotaResetsAt` and `setQuotaResetsAt` in the hook's return.

In `streamHandlers.ts` `onError` (currently sets the banner via `chatErrorMessage`):

```typescript
    onError: (detail, code, resetsAt) => {
      setLiveStatus(null)
      if (code === 'quota_exceeded') {
        // Mirror the server-persisted marker (Task 2) instead of the banner,
        // and arm the composer lock for this session.
        appendMessage({ id: localId('quota'), role: 'quota_refusal', content: detail })
        setQuotaResetsAt(resetsAt ?? null)
        return
      }
      setError(chatErrorMessage(detail, code, resetsAt))
    },
```

(`appendMessage`/`localId` are the same primitives the `cancelled` path uses in `useAssistantChat.ts:96-104` — thread them into the handlers args the same way `setError` already is.)

In `AssistantComposer.tsx`: add prop `quotaNotice?: string | null`; `const disabled = sending || blocked || Boolean(quotaNotice)`; in `composerPlaceholder`, return `quotaNotice` first when present; reuse the existing amber notice block (`:40-44`) to also show `quotaNotice` above the input.

In `AssistantChat.tsx`: `const usage = useMeUsage()` and pass `quotaNotice={quotaLock(usage.data, chat.quotaResetsAt)}` to the composer — derived in render, no effects.

- [ ] **Step 5: Component test**

Colocate with the composer's existing test file if present, else create `frontend/src/features/assistant/components/AssistantComposer.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AssistantComposer } from './AssistantComposer'

const NOTICE = 'Monthly AI limit reached — resets August 1, 2026'

describe('AssistantComposer quota lock', () => {
  it('disables input and shows the notice when quotaNotice is set', () => {
    render(
      <AssistantComposer
        draft=""
        setDraft={vi.fn()}
        sending={false}
        status={null}
        blocked={false}
        quotaNotice={NOTICE}
        onSend={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const textarea = screen.getByRole('textbox')
    expect(textarea).toBeDisabled()
    expect(textarea).toHaveAttribute('placeholder', NOTICE)
    expect(screen.getByText(NOTICE)).toBeInTheDocument()
  })

  it('stays enabled without a quotaNotice', () => {
    render(
      <AssistantComposer
        draft=""
        setDraft={vi.fn()}
        sending={false}
        status={null}
        blocked={false}
        quotaNotice={null}
        onSend={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByRole('textbox')).toBeEnabled()
  })
})
```

(Match the prop list to the merged `AssistantComposer` signature — `status`'s type may be `string | null` or narrower.)

- [ ] **Step 6: Gates + commit**

```bash
npm run test
npm run lint
npm run build
printf 'feat: durable chat quota refusal note and informed composer lock\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
