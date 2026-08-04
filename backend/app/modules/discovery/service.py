"""Discovery business logic — title search + persist candidates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.normalize import normalize_title
from app.modules.discovery.exceptions import (
    DiscoveredBookNotFoundError,
    DiscoveryRecommendError,
)
from app.modules.discovery.models import BookSource, DiscoveredBook
from app.modules.discovery.ranking import rank_sources
from app.modules.discovery.recommend import (
    cap_queries,
    clamp_recommend_limit,
    evidence_for,
    score_candidate,
    summary_keyword_queries,
    theme_tokens,
)
from app.modules.discovery.repository import DiscoveryRepository
from app.modules.discovery.schemas import (
    BookSourceRead,
    DiscoveredBookRead,
    DiscoveryRecommendItem,
    DiscoveryRecommendResponse,
    DiscoverySearchResponse,
)
from app.modules.discovery.sources.registry import search_all_sources
from app.modules.discovery.types import ExternalSearchHit
from app.modules.library.service import LibraryService
from app.modules.llm.service import LlmService

_DEFAULT_LIMIT = 8
_SEARCH_CONCURRENCY = 2
_EARLY_STOP_MULTIPLIER = 2


@dataclass(frozen=True, slots=True)
class _RecommendEvidence:
    """Theme / index / query-hit reasons for ranking evidence strings."""

    query_hits: dict[str, list[str]]
    index_notes: dict[str, list[str]]
    themes: list[str]


class DiscoveryService:
    """Owns discovery search and candidate upsert."""

    def __init__(
        self,
        session: AsyncSession,
        llm: LlmService | None = None,
        *,
        conversation_id: UUID | None = None,
    ) -> None:
        self._session = session
        self._repo = DiscoveryRepository(session)
        self._library = LibraryService(session)
        self._llm = llm
        self._conversation_id = conversation_id

    async def search_by_title(
        self,
        user_id: UUID,
        query: str,
        *,
        external: bool = True,
        limit: int = _DEFAULT_LIMIT,
    ) -> DiscoverySearchResponse:
        """Search internal candidates; optionally refresh from all scrape sources."""
        cleaned = query.strip()
        if not cleaned:
            return DiscoverySearchResponse(query=cleaned, results=[])
        if external:
            await self._ingest_external(cleaned)
            await self._session.commit()
        books = await self._repo.search_by_title(normalize_title(cleaned), limit=limit)
        owned = await self._owned_titles(user_id)
        return DiscoverySearchResponse(
            query=cleaned,
            results=await self._to_reads(books, owned),
        )

    async def recommend(
        self,
        user_id: UUID,
        *,
        seed_book_id: UUID | None = None,
        themes: list[str] | None = None,
        candidate_titles: list[str] | None = None,
        limit: int = 3,
        exclude_owned: bool = True,
    ) -> DiscoveryRecommendResponse:
        """Batch title searches for recommendation-style prompts."""
        limit = clamp_recommend_limit(limit)
        theme_list = [t.strip() for t in (themes or []) if t.strip()]
        queries, index_notes = await self._build_recommend_queries(
            user_id,
            seed_book_id=seed_book_id,
            candidate_titles=candidate_titles or [],
            themes=theme_list,
        )
        query_hits = await self._ingest_recommend_queries(
            queries,
            target=limit * _EARLY_STOP_MULTIPLIER,
        )
        await self._session.commit()
        owned = await self._owned_titles(user_id)
        books = await self._collect_recommend_books(queries, query_hits)
        ranked = await self._rank_recommend_books(
            books,
            queries=queries,
            owned=owned,
            exclude_owned=exclude_owned,
            limit=limit,
            evidence=_RecommendEvidence(
                query_hits=query_hits,
                index_notes=index_notes,
                themes=theme_list,
            ),
        )
        if not ranked:
            raise DiscoveryRecommendError(
                "Researched titles were not found on supported scrape sources. "
                "Retry or pass known English candidate_titles."
            )
        reads = await self._to_reads([item[0] for item in ranked], owned)
        by_id = {row.id: row for row in reads}
        return DiscoveryRecommendResponse(
            queries=queries,
            themes=theme_list,
            limit=limit,
            results=[
                DiscoveryRecommendItem(
                    book=by_id[book.id],
                    evidence=evidence,
                    scrapable_chapters=_scrapable_chapters(by_id[book.id]),
                )
                for book, evidence in ranked
                if book.id in by_id
            ],
        )

    async def get_book(self, user_id: UUID, book_id: UUID) -> DiscoveredBookRead:
        """Load one discovered book with ranked sources."""
        book = await self._repo.get_book(book_id)
        if book is None:
            raise DiscoveredBookNotFoundError(str(book_id))
        owned = await self._owned_titles(user_id)
        rows = await self._to_reads([book], owned)
        return rows[0]

    async def pick_source(
        self,
        user_id: UUID,
        book_id: UUID,
        source_id: UUID | None = None,
    ) -> tuple[DiscoveredBookRead, BookSourceRead]:
        """Resolve a source for import — explicit id or richest estimate."""
        book = await self.get_book(user_id, book_id)
        if not book.sources:
            raise DiscoveredBookNotFoundError(f"{book_id}:no-sources")
        if source_id is None:
            return book, book.sources[0]
        for src in book.sources:
            if src.id == source_id:
                return book, src
        raise DiscoveredBookNotFoundError(f"{book_id}:source:{source_id}")

    async def _build_recommend_queries(
        self,
        user_id: UUID,
        *,
        seed_book_id: UUID | None,
        candidate_titles: list[str],
        themes: list[str],
    ) -> tuple[list[str], dict[str, list[str]]]:
        if not candidate_titles and seed_book_id is None and not themes:
            raise DiscoveryRecommendError("Pass candidate_titles, seed_book_id, and/or themes")
        seed_title, seed_norm = await self._seed_title_pair(user_id, seed_book_id)
        queries = _similar_candidate_titles(candidate_titles, themes=themes, seed_norm=seed_norm)
        theme_list = list(themes)
        if seed_book_id is not None and not theme_list:
            theme_list.extend(await self._cached_summary_queries(user_id, seed_book_id))
        index_notes: dict[str, list[str]] = {}
        await self._expand_from_indexes(
            queries,
            index_notes,
            user_id=user_id,
            themes=theme_list,
            seed_title=seed_title,
        )
        if seed_norm is not None:
            queries = [q for q in queries if normalize_title(q) != seed_norm]
        capped = cap_queries(queries)
        if not capped:
            raise DiscoveryRecommendError(
                "Title research did not return usable titles. "
                "Retry later or pass other English candidate_titles."
            )
        return capped, index_notes

    async def _seed_title_pair(
        self,
        user_id: UUID,
        seed_book_id: UUID | None,
    ) -> tuple[str | None, str | None]:
        if seed_book_id is None:
            return None, None
        book = await self._library.get_book(user_id, seed_book_id)
        return book.title, normalize_title(book.title)

    async def _expand_from_indexes(
        self,
        queries: list[str],
        index_notes: dict[str, list[str]],
        *,
        user_id: UUID,
        themes: list[str],
        seed_title: str | None,
    ) -> None:
        needs_research = bool(themes or seed_title)
        if not needs_research:
            return
        if self._llm is None:
            raise DiscoveryRecommendError(
                "Theme/seed discovery requires title research (LLM not configured)"
            )
        from app.modules.discovery.indexes.research import titles_from_research

        hits = await titles_from_research(
            self._llm,
            user_id=user_id,
            themes=themes,
            seed_title=seed_title,
            conversation_id=self._conversation_id,
        )
        for hit in hits:
            _append_index_title(queries, index_notes, hit.title, hit.note)

    async def _cached_summary_queries(self, user_id: UUID, book_id: UUID) -> list[str]:
        from app.modules.summaries.schemas import SummaryKind
        from app.modules.summaries.service import SummaryService

        lookup = await SummaryService(self._session).lookup(
            user_id,
            book_id,
            SummaryKind.NO_SPOILER,
        )
        if lookup.summary is None:
            return []
        return summary_keyword_queries(lookup.summary.structured_data)

    async def _ingest_recommend_queries(
        self,
        queries: list[str],
        *,
        target: int,
    ) -> dict[str, list[str]]:
        """Search sources (concurrency 2); upsert sequentially; early-stop."""
        evidence: dict[str, list[str]] = {}
        for start in range(0, len(queries), _SEARCH_CONCURRENCY):
            batch = queries[start : start + _SEARCH_CONCURRENCY]
            hits_by_query = await asyncio.gather(*(_safe_search(q) for q in batch))
            for query, hits in zip(batch, hits_by_query, strict=True):
                await self._apply_hits(query, hits, evidence)
            if len(evidence) >= target:
                break
        return evidence

    async def _apply_hits(
        self,
        query: str,
        hits: list[ExternalSearchHit],
        evidence: dict[str, list[str]],
    ) -> None:
        for hit in hits:
            await self._upsert_hit(hit)
            key = normalize_title(hit.title)
            seen = evidence.setdefault(key, [])
            if query not in seen:
                seen.append(query)

    async def _collect_recommend_books(
        self,
        queries: list[str],
        query_hits: dict[str, list[str]],
    ) -> list[DiscoveredBook]:
        by_id: dict[UUID, DiscoveredBook] = {}
        for query in queries:
            for book in await self._repo.search_by_title(normalize_title(query), limit=12):
                by_id[book.id] = book
        for normalized in query_hits:
            found = await self._repo.find_by_normalized_title(normalized)
            if found is not None:
                by_id[found.id] = found
        return list(by_id.values())

    async def _rank_recommend_books(
        self,
        books: list[DiscoveredBook],
        *,
        queries: list[str],
        owned: set[str],
        exclude_owned: bool,
        limit: int,
        evidence: _RecommendEvidence,
    ) -> list[tuple[DiscoveredBook, list[str]]]:
        if exclude_owned:
            books = [b for b in books if b.normalized_title not in owned]
        sources = await self._repo.list_sources([book.id for book in books])
        by_book: dict[UUID, list[BookSource]] = {book.id: [] for book in books}
        for src in sources:
            by_book.setdefault(src.discovered_book_id, []).append(src)
        books = [b for b in books if by_book.get(b.id)]
        theme_set = theme_tokens(evidence.themes)
        scored = sorted(
            books,
            key=lambda book: score_candidate(
                book,
                by_book.get(book.id, []),
                queries=queries,
                themes=theme_set,
            ),
            reverse=True,
        )
        return [
            (
                book,
                evidence_for(
                    book,
                    query_hits=evidence.query_hits,
                    themes=evidence.themes,
                    index_notes=evidence.index_notes,
                ),
            )
            for book in scored[:limit]
        ]

    async def _ingest_external(self, query: str) -> None:
        for hit in await search_all_sources(query):
            await self._upsert_hit(hit)

    async def _upsert_hit(self, hit: ExternalSearchHit) -> None:
        existing_source = await self._repo.get_source_by_url(hit.source, hit.book_url)
        if existing_source is not None:
            if hit.chapter_count_estimate is not None:
                existing_source.chapter_count_estimate = hit.chapter_count_estimate
            return
        normalized = normalize_title(hit.title)
        book = await self._repo.find_by_normalized_title(normalized)
        if book is None:
            book = await self._repo.add_book(
                DiscoveredBook(
                    title=hit.title.strip(),
                    normalized_title=normalized,
                    author=hit.author.strip(),
                )
            )
        await self._repo.add_source(
            BookSource(
                discovered_book_id=book.id,
                source=hit.source,
                book_url=hit.book_url,
                first_chapter_url=hit.first_chapter_url,
                chapter_count_estimate=hit.chapter_count_estimate,
            )
        )

    async def _owned_titles(self, user_id: UUID) -> set[str]:
        books = await self._library.list_books(user_id)
        return {normalize_title(book.title) for book in books}

    async def _to_reads(
        self,
        books: list[DiscoveredBook],
        owned: set[str],
    ) -> list[DiscoveredBookRead]:
        sources = await self._repo.list_sources([book.id for book in books])
        by_book: dict[UUID, list[BookSource]] = {book.id: [] for book in books}
        for src in sources:
            by_book.setdefault(src.discovered_book_id, []).append(src)
        return [
            DiscoveredBookRead(
                id=book.id,
                title=book.title,
                author=book.author,
                description=book.description,
                language=book.language,
                already_owned=book.normalized_title in owned,
                sources=_ranked_source_reads(by_book.get(book.id, [])),
                created_at=book.created_at,
                updated_at=book.updated_at,
            )
            for book in books
        ]


def _ranked_source_reads(sources: list[BookSource]) -> list[BookSourceRead]:
    ranked = rank_sources(sources)
    return [
        BookSourceRead.model_validate(src).model_copy(update={"recommended": index == 0})
        for index, src in enumerate(ranked)
    ]


def _scrapable_chapters(book: DiscoveredBookRead) -> int | None:
    estimates = [s.chapter_count_estimate for s in book.sources if s.chapter_count_estimate]
    return max(estimates) if estimates else None


def _append_index_title(
    queries: list[str],
    index_notes: dict[str, list[str]],
    title: str,
    note: str,
) -> None:
    cleaned = " ".join(title.split()).strip()
    if not cleaned:
        return
    queries.append(cleaned)
    key = normalize_title(cleaned)
    notes = index_notes.setdefault(key, [])
    if note not in notes:
        notes.append(note)


def _similar_candidate_titles(
    candidate_titles: list[str],
    *,
    themes: list[str],
    seed_norm: str | None,
) -> list[str]:
    """Titles safe to scrape-search for similarity (not the seed / lone lookalike)."""
    cleaned = [t.strip() for t in candidate_titles if t.strip()]
    if themes and len(cleaned) <= 1:
        # Lone title + themes ⇒ seed name from the model; searching it finds lookalikes.
        return []
    out: list[str] = []
    for title in cleaned:
        if seed_norm is not None and normalize_title(title) == seed_norm:
            continue
        out.append(title)
    return out


async def _safe_search(query: str) -> list[ExternalSearchHit]:
    try:
        return await search_all_sources(query)
    except Exception:
        # search_all_sources already swallows per-source failures; this is belt-and-braces
        return []
