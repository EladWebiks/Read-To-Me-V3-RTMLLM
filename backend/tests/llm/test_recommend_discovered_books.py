"""Unit tests for recommend_discovered_books tool + service batching."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.modules.discovery.exceptions import DiscoveryRecommendError
from app.modules.discovery.indexes.research import ResearchTitleHit
from app.modules.discovery.models import DiscoveredBook
from app.modules.discovery.schemas import (
    BookSourceRead,
    DiscoveredBookRead,
    DiscoveryRecommendItem,
)
from app.modules.discovery.service import DiscoveryService, RecommendSpec
from app.modules.discovery.types import ExternalSearchHit
from app.modules.tools.base import Mode, ToolContext
from app.modules.tools.catalog import build_default_registry
from app.modules.tools.definitions.recommend_discovered_books import (
    RecommendDiscoveredBooksInput,
    RecommendDiscoveredBooksOutput,
    RecommendDiscoveredBooksTool,
)
from app.modules.tools.exceptions import ToolValidationError
from pydantic import ValidationError


@pytest.mark.unit
def test_recommend_visible_only_in_external_mode() -> None:
    registry = build_default_registry()
    internal = {s.name for s in registry.list_specs(Mode.INTERNAL_ONLY)}
    external = {s.name for s in registry.list_specs(Mode.EXTERNAL_ALLOWED)}
    assert "recommend_discovered_books" not in internal
    assert "recommend_discovered_books" in external
    assert "search_discovered_books" in external


@pytest.mark.unit
def test_recommend_input_requires_bounded_lists() -> None:
    with pytest.raises(ValidationError):
        RecommendDiscoveredBooksInput.model_validate({"limit": 0})
    with pytest.raises(ValidationError):
        RecommendDiscoveredBooksInput.model_validate(
            {"candidate_titles": [f"t{i}" for i in range(26)]}
        )
    with pytest.raises(ValidationError):
        RecommendDiscoveredBooksInput.model_validate({"limit": 26})
    ok = RecommendDiscoveredBooksInput.model_validate(
        {"candidate_titles": ["A", "B"], "limit": 20}
    )
    assert ok.limit == 20


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommend_tool_rejects_empty_request() -> None:
    tool = RecommendDiscoveredBooksTool()
    ctx = ToolContext(
        user_id=uuid4(),
        conversation_id=uuid4(),
        run_id=uuid4(),
        mode=Mode.EXTERNAL_ALLOWED,
        session=MagicMock(),
    )
    with (
        patch(
            "app.modules.tools.definitions.recommend_discovered_books.prior_recommend_exclude_titles",
            new=AsyncMock(return_value=[]),
        ),
        patch("app.modules.tools.definitions.recommend_discovered_books.DiscoveryService") as svc,
        patch("app.modules.tools.definitions.recommend_discovered_books.LlmService"),
        patch("app.modules.tools.definitions.recommend_discovered_books.get_settings"),
    ):
        svc.return_value.recommend = AsyncMock(
            side_effect=DiscoveryRecommendError("Pass candidate_titles")
        )
        with pytest.raises(ToolValidationError):
            await tool.execute(RecommendDiscoveredBooksInput(), ctx)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommend_tool_merges_prior_excludes() -> None:
    tool = RecommendDiscoveredBooksTool()
    ctx = _tool_ctx()
    recommend = AsyncMock(return_value=_recommend_stub())
    with (
        patch(
            "app.modules.tools.definitions.recommend_discovered_books.prior_recommend_exclude_titles",
            new=AsyncMock(return_value=["Coiling Dragon", "The Desolate Era"]),
        ),
        patch("app.modules.tools.definitions.recommend_discovered_books.DiscoveryService") as svc,
        patch("app.modules.tools.definitions.recommend_discovered_books.LlmService"),
        patch("app.modules.tools.definitions.recommend_discovered_books.get_settings"),
    ):
        svc.return_value.recommend = recommend
        out = await tool.execute(
            RecommendDiscoveredBooksInput(
                themes=["cultivation"],
                limit=20,
                exclude_titles=["Desolate Era"],
            ),
            ctx,
        )
    assert isinstance(out, RecommendDiscoveredBooksOutput)
    assert out.count == 1
    assert out.results[0].title == "Martial Peak"
    assert out.results[0].discovered_book_id is not None
    assert recommend.await_args is not None
    excluded = recommend.await_args.args[1].exclude_titles
    assert "Coiling Dragon" in excluded
    assert len([t for t in excluded if "desolate" in t.lower()]) == 1


@pytest.mark.unit
def test_recommend_slim_payload_stays_small() -> None:
    """Fat nested book dumps were truncated mid-JSON (model then echoed ']}')."""
    from app.modules.tools.definitions.recommend_discovered_books import RecommendListItem

    rows = [
        RecommendListItem(
            discovered_book_id=uuid4(),
            title=f"Title {i}",
            author="Author",
            scrapable_chapters=1000 + i,
            source="novelfull",
            premise="short premise",
        )
        for i in range(20)
    ]
    payload = RecommendDiscoveredBooksOutput(
        themes=["xianxia"],
        count=20,
        results=rows,
        message="Found 20\n"
        + "\n".join(f"- {r.title} — {r.author} — ~{r.scrapable_chapters} chapters" for r in rows),
    )
    assert len(payload.model_dump_json()) < 12_000


@pytest.mark.unit
def test_recommend_message_row_includes_exact_book_url() -> None:
    from app.modules.tools.definitions.recommend_discovered_books import _table_row

    stub = _recommend_stub().results[0]
    stub.book.sources[0].book_url = "https://ranobes.top/novels/244924-reverend-insanity.html"
    stub.book.sources[0].source = "ranobes"
    row = _table_row(stub)
    assert "url: https://ranobes.top/novels/244924-reverend-insanity.html" in row
    assert "Martial Peak" in row


def _tool_ctx() -> ToolContext:
    return ToolContext(
        user_id=uuid4(),
        conversation_id=uuid4(),
        run_id=uuid4(),
        mode=Mode.EXTERNAL_ALLOWED,
        session=MagicMock(),
    )


def _recommend_stub() -> MagicMock:
    now = datetime.now(UTC)
    book_id = uuid4()
    item = DiscoveryRecommendItem(
        book=DiscoveredBookRead(
            id=book_id,
            title="Martial Peak",
            author="Momo",
            description="",
            language="en",
            sources=[
                BookSourceRead(
                    id=uuid4(),
                    source="novelfull",
                    book_url="https://example.com/x",
                    first_chapter_url="https://example.com/x/1",
                    chapter_count_estimate=100,
                    created_at=now,
                    updated_at=now,
                )
            ],
            created_at=now,
            updated_at=now,
        ),
        evidence=["title research"],
        scrapable_chapters=100,
    )
    return MagicMock(queries=["Martial Peak"], themes=["cultivation"], results=[item])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommend_themes_only_expands_via_title_research() -> None:
    llm = MagicMock()
    service, searched, books = _mock_recommend_service(llm=llm)
    books["Martial Peak"] = _discovered("Martial Peak")

    async def collect(
        _queries: list[str],
        _query_hits: dict[str, list[str]],
    ) -> list[DiscoveredBook]:
        return [books["Martial Peak"]]

    with (
        patch(
            "app.modules.discovery.service.titles_from_research",
            new=AsyncMock(
                return_value=[
                    ResearchTitleHit(
                        title="Martial Peak",
                        note="title research: classic cultivation progression",
                    )
                ]
            ),
        ),
        patch(
            "app.modules.discovery.service.search_all_sources",
            side_effect=_search_side_effect(searched),
        ),
        patch.object(service, "_collect_recommend_books", side_effect=collect),
    ):
        result = await service.recommend(
            uuid4(),
            RecommendSpec(themes=("cultivation",), limit=3, exclude_owned=True),
        )
    assert "Martial Peak" in searched
    assert result.results[0].book.title == "Martial Peak"
    assert any("title research" in e for e in result.results[0].evidence)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommend_themes_hard_fails_when_research_empty() -> None:
    llm = MagicMock()
    service, _searched, _books = _mock_recommend_service(llm=llm)
    with (
        patch(
            "app.modules.discovery.service.titles_from_research",
            new=AsyncMock(return_value=[]),
        ),
        pytest.raises(DiscoveryRecommendError, match="Title research did not return"),
    ):
        await service.recommend(uuid4(), RecommendSpec(themes=("cultivation",), limit=3))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommend_themes_require_llm() -> None:
    service, _searched, _books = _mock_recommend_service(llm=None)
    with pytest.raises(DiscoveryRecommendError, match="requires title research"):
        await service.recommend(uuid4(), RecommendSpec(themes=("cultivation",), limit=3))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommend_hard_fails_when_no_scrapable_hits() -> None:
    llm = MagicMock()
    service, searched, _books = _mock_recommend_service(llm=llm)

    with (
        patch(
            "app.modules.discovery.service.titles_from_research",
            new=AsyncMock(
                return_value=[ResearchTitleHit(title="Missing Novel", note="title research")]
            ),
        ),
        patch(
            "app.modules.discovery.service.search_all_sources",
            side_effect=_search_side_effect(searched),
        ),
        pytest.raises(DiscoveryRecommendError, match="not found on supported scrape"),
    ):
        await service.recommend(uuid4(), RecommendSpec(themes=("cultivation",), limit=3))
    assert "Missing Novel" in searched


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommend_refills_research_when_scrapable_short() -> None:
    llm = MagicMock()
    service, searched, books = _mock_recommend_service(llm=llm)
    books.clear()
    service._repo.add_book = AsyncMock(side_effect=_persist_book(books))  # type: ignore[method-assign]
    research = AsyncMock(side_effect=_refill_research_batches())
    with (
        patch("app.modules.discovery.service.titles_from_research", new=research),
        patch(
            "app.modules.discovery.service.search_all_sources",
            side_effect=_search_side_effect(searched),
        ),
    ):
        result = await service.recommend(
            uuid4(),
            RecommendSpec(themes=("xianxia",), limit=2, exclude_owned=True),
        )
    assert research.await_count == 2
    assert {row.book.title for row in result.results} == {"Martial Peak", "Coiling Dragon"}
    assert {"Ghost Novel", "Martial Peak", "Coiling Dragon"} <= set(searched)


def _persist_book(books: dict[str, DiscoveredBook]) -> object:
    async def add_book(book: DiscoveredBook) -> DiscoveredBook:
        if book.id is None:
            book.id = uuid4()
        book.description = book.description or ""
        book.language = book.language or "en"
        book.created_at = book.created_at or datetime.now(UTC)
        book.updated_at = book.updated_at or book.created_at
        books[book.title] = book
        return book

    return add_book


def _refill_research_batches() -> list[list[ResearchTitleHit]]:
    return [
        [ResearchTitleHit(title="Ghost Novel", note="title research: missing")],
        [
            ResearchTitleHit(title="Martial Peak", note="title research: classic"),
            ResearchTitleHit(title="Coiling Dragon", note="title research: classic"),
        ],
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommend_service_one_batch_covers_many_titles() -> None:
    llm = MagicMock()
    service, searched, books = _mock_recommend_service(llm=llm)

    async def collect(
        _queries: list[str],
        _query_hits: dict[str, list[str]],
    ) -> list[DiscoveredBook]:
        return list(books.values())

    with (
        patch(
            "app.modules.discovery.service.titles_from_research",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.modules.discovery.service.search_all_sources",
            side_effect=_search_side_effect(searched),
        ),
        patch.object(service, "_collect_recommend_books", side_effect=collect),
    ):
        result = await service.recommend(
            uuid4(),
            RecommendSpec(
                candidate_titles=("Book One", "Book Two", "Owned Tale"),
                themes=("cultivation",),
                limit=3,
                exclude_owned=True,
            ),
        )
    assert "Book One" in searched
    assert "Book Two" in searched
    assert {row.book.title for row in result.results} == {"Book One", "Book Two"}
    assert all(row.evidence for row in result.results)


def _mock_recommend_service(
    llm: object | None = None,
) -> tuple[DiscoveryService, list[str], dict[str, DiscoveredBook]]:
    session = MagicMock()
    session.commit = AsyncMock()
    service = DiscoveryService(session, llm)  # type: ignore[arg-type]
    books = {
        "Book One": _discovered("Book One"),
        "Book Two": _discovered("Book Two"),
        "Owned Tale": _discovered("Owned Tale"),
    }
    searched: list[str] = []

    async def find_by_title(normalized: str) -> DiscoveredBook | None:
        for book in books.values():
            if book.normalized_title == normalized:
                return book
        return None

    service._repo = MagicMock()
    service._repo.get_source_by_url = AsyncMock(return_value=None)
    service._repo.find_by_normalized_title = AsyncMock(side_effect=find_by_title)
    service._repo.add_book = AsyncMock(side_effect=lambda book: book)
    service._repo.add_source = AsyncMock()
    service._repo.search_by_title = AsyncMock(return_value=[])
    service._repo.list_sources = AsyncMock(side_effect=_fake_sources)
    service._owned_titles = AsyncMock(return_value={"owned tale"})  # type: ignore[method-assign]
    return service, searched, books


async def _fake_sources(book_ids: list[object]) -> list[MagicMock]:
    out: list[MagicMock] = []
    for book_id in book_ids:
        src = MagicMock()
        src.discovered_book_id = book_id
        src.source = "novelfull"
        src.book_url = "https://example.com/x"
        src.first_chapter_url = "https://example.com/x/1"
        src.chapter_count_estimate = 100
        src.id = uuid4()
        src.created_at = datetime.now(UTC)
        src.updated_at = datetime.now(UTC)
        out.append(src)
    return out


def _search_side_effect(searched: list[str]) -> object:
    by_title = {
        "Book One": _hit("Book One", "novelfull", 100),
        "Book Two": _hit("Book Two", "novelbin", 200),
        "Owned Tale": _hit("Owned Tale", "novellunar", 50),
        "Martial Peak": _hit("Martial Peak", "novelfull", 5000),
        "Coiling Dragon": _hit("Coiling Dragon", "novelfull", 800),
    }

    async def fake_search(query: str) -> list[ExternalSearchHit]:
        searched.append(query)
        hit = by_title.get(query)
        return [hit] if hit is not None else []

    return fake_search


def _hit(title: str, source: str, chapters: int) -> ExternalSearchHit:
    return ExternalSearchHit(
        title=title,
        author="A",
        source=source,
        book_url=f"https://example.com/{title}",
        first_chapter_url=f"https://example.com/{title}/1",
        chapter_count_estimate=chapters,
    )


def _discovered(title: str) -> DiscoveredBook:
    now = datetime.now(UTC)
    return DiscoveredBook(
        id=uuid4(),
        title=title,
        normalized_title=title.lower(),
        author="Author",
        description="",
        language="en",
        created_at=now,
        updated_at=now,
    )
