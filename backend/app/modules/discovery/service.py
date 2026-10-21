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
from app.modules.discovery.indexes.research import TitleResearchSpec, titles_from_research
from app.modules.discovery.models import BookSource, DiscoveredBook
from app.modules.discovery.ranking import rank_sources
from app.modules.discovery.recommend import (
    cap_queries,
    clamp_recommend_limit,
    dedupe_by_exclude_key,
    evidence_for,
    exclude_title_key,
    is_derivative_title,
    matches_recommend_query,
    passes_source_and_chapters,
    prefer_source_rows,
    score_candidate,
    source_chapter_estimate,
    summary_keyword_queries,
    theme_tokens,
    without_excluded_sources,
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
from app.modules.scraping.registry import SOURCE_DOMAINS

_DEFAULT_LIMIT = 8
_SEARCH_CONCURRENCY = 2
_RESEARCH_POOL = 25
_MAX_REFILL_ROUNDS = 2
# Search cards often expose a partial TOC size; below this, treat as unknown in recommend.
_MIN_RELIABLE_CHAPTER_ESTIMATE = 100


@dataclass(frozen=True, slots=True)
class RecommendSpec:
    """Inputs for a batched discovery recommendation."""

    seed_book_id: UUID | None = None
    themes: tuple[str, ...] = ()
    candidate_titles: tuple[str, ...] = ()
    limit: int = 3
    exclude_owned: bool = True
    exclude_titles: tuple[str, ...] = ()
    source: str | None = None
    exclude_sources: tuple[str, ...] = ()
    min_chapters: int | None = None


@dataclass(frozen=True, slots=True)
class _RecommendEvidence:
    """Theme / index / query-hit reasons for ranking evidence strings."""

    query_hits: dict[str, list[str]]
    index_notes: dict[str, list[str]]
    themes: list[str]


@dataclass(frozen=True, slots=True)
class _RecommendFilters:
    """Ownership / prior-suggestion / source exclusions for ranking."""

    exclude_owned: bool
    exclude_titles: tuple[str, ...]
    source: str | None = None
    exclude_sources: frozenset[str] = frozenset()
    min_chapters: int | None = None


@dataclass(slots=True)
class _RecommendState:
    """Mutable batch state across research → scrape → refill rounds."""

    queries: list[str]
    index_notes: dict[str, list[str]]
    themes: list[str]
    seed_title: str | None
    excluded: list[str]
    ingested: set[str]
    query_hits: dict[str, list[str]]


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
        spec: RecommendSpec,
    ) -> DiscoveryRecommendResponse:
        """Batch title searches for recommendation-style prompts."""
        limit = clamp_recommend_limit(spec.limit)
        preferred = _normalize_source_name(spec.source)
        excluded = _normalize_source_names(spec.exclude_sources)
        if preferred is not None and preferred in excluded:
            raise DiscoveryRecommendError(
                f"Cannot require source '{preferred}' while also excluding it."
            )
        filtered = RecommendSpec(
            seed_book_id=spec.seed_book_id,
            themes=spec.themes,
            candidate_titles=spec.candidate_titles,
            limit=spec.limit,
            exclude_owned=spec.exclude_owned,
            exclude_titles=spec.exclude_titles,
            source=preferred,
            exclude_sources=tuple(sorted(excluded)),
            min_chapters=spec.min_chapters,
        )
        state = await self._start_recommend(user_id, filtered, limit=limit)
        ranked = await self._fill_recommend(user_id, filtered, state, limit=limit)
        if not ranked:
            raise DiscoveryRecommendError(
                "Researched titles were not found on supported scrape sources. "
                "Retry or pass known English candidate_titles."
            )
        owned = await self._owned_titles(user_id)
        reads = await self._to_reads([item[0] for item in ranked], owned)
        by_id = {
            row.id: row.model_copy(
                update={
                    "sources": prefer_source_rows(
                        without_excluded_sources(row.sources, excluded),
                        preferred,
                    )
                }
            )
            for row in reads
        }
        return DiscoveryRecommendResponse(
            queries=state.queries,
            themes=state.themes,
            limit=limit,
            results=[
                DiscoveryRecommendItem(
                    book=by_id[book.id],
                    evidence=evidence,
                    scrapable_chapters=_scrapable_chapters(
                        by_id[book.id],
                        preferred=preferred,
                    ),
                )
                for book, evidence in ranked
                if book.id in by_id and by_id[book.id].sources
            ],
        )

    async def _start_recommend(
        self,
        user_id: UUID,
        spec: RecommendSpec,
        *,
        limit: int,
    ) -> _RecommendState:
        excluded = [t.strip() for t in spec.exclude_titles if t.strip()]
        queries, index_notes, themes, seed_title = await self._build_recommend_queries(
            user_id,
            spec,
            research_limit=_RESEARCH_POOL if (spec.themes or spec.seed_book_id) else limit,
        )
        return _RecommendState(
            queries=queries,
            index_notes=index_notes,
            themes=themes,
            seed_title=seed_title,
            excluded=excluded,
            ingested=set(),
            query_hits={},
        )

    async def _fill_recommend(
        self,
        user_id: UUID,
        spec: RecommendSpec,
        state: _RecommendState,
        *,
        limit: int,
    ) -> list[tuple[DiscoveredBook, list[str]]]:
        owned = await self._owned_titles(user_id)
        ranked: list[tuple[DiscoveredBook, list[str]]] = []
        for _ in range(_MAX_REFILL_ROUNDS + 1):
            await self._ingest_pending_queries(state, target=limit)
            await self._session.commit()
            books = await self._collect_recommend_books(state.queries, state.query_hits)
            ranked = await self._rank_recommend_books(
                books,
                queries=state.queries,
                owned=owned,
                filters=_RecommendFilters(
                    exclude_owned=spec.exclude_owned,
                    exclude_titles=tuple(state.excluded),
                    source=spec.source,
                    exclude_sources=frozenset(spec.exclude_sources),
                    min_chapters=spec.min_chapters,
                ),
                limit=limit,
                evidence=_RecommendEvidence(
                    query_hits=state.query_hits,
                    index_notes=state.index_notes,
                    themes=state.themes,
                ),
            )
            if len(ranked) >= limit:
                return ranked
            if not await self._refill_recommend_queries(user_id, state, need=limit - len(ranked)):
                break
        return ranked

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
        *,
        exclude_sources: tuple[str, ...] = (),
    ) -> tuple[DiscoveredBookRead, BookSourceRead]:
        """Resolve a source for import — explicit id or richest estimate."""
        book = await self.get_book(user_id, book_id)
        excluded = _normalize_source_names(exclude_sources)
        candidates = without_excluded_sources(book.sources, excluded)
        if not candidates:
            names = ", ".join(sorted(excluded)) or "(none)"
            raise DiscoveredBookNotFoundError(f"{book_id}:no-sources-after-exclude:{names}")
        if source_id is None:
            return book, candidates[0]
        for src in candidates:
            if src.id == source_id:
                return book, src
        raise DiscoveredBookNotFoundError(f"{book_id}:source:{source_id}")

    async def _build_recommend_queries(
        self,
        user_id: UUID,
        spec: RecommendSpec,
        *,
        research_limit: int,
    ) -> tuple[list[str], dict[str, list[str]], list[str], str | None]:
        candidate_titles = list(spec.candidate_titles)
        themes = [t.strip() for t in spec.themes if t.strip()]
        exclude_titles = [t.strip() for t in spec.exclude_titles if t.strip()]
        if not candidate_titles and spec.seed_book_id is None and not themes:
            raise DiscoveryRecommendError("Pass candidate_titles, seed_book_id, and/or themes")
        seed_title, seed_norm = await self._seed_title_pair(user_id, spec.seed_book_id)
        queries = _similar_candidate_titles(candidate_titles, themes=themes, seed_norm=seed_norm)
        theme_list = list(themes)
        if spec.seed_book_id is not None and not theme_list:
            theme_list.extend(await self._cached_summary_queries(user_id, spec.seed_book_id))
        index_notes: dict[str, list[str]] = {}
        await self._expand_from_indexes(
            queries,
            index_notes,
            user_id=user_id,
            research=TitleResearchSpec(
                themes=tuple(theme_list),
                seed_title=seed_title,
                limit=research_limit,
                exclude_titles=tuple(exclude_titles),
            ),
        )
        excluded = {exclude_title_key(t) for t in exclude_titles}
        if seed_norm is not None:
            excluded.add(exclude_title_key(seed_norm))
        queries = [q for q in queries if exclude_title_key(q) not in excluded]
        capped = cap_queries(queries)
        if not capped:
            raise DiscoveryRecommendError(
                "Title research did not return usable titles. "
                "Retry later or pass other English candidate_titles."
            )
        return capped, index_notes, theme_list, seed_title

    async def _refill_recommend_queries(
        self,
        user_id: UUID,
        state: _RecommendState,
        *,
        need: int,
    ) -> bool:
        if need <= 0 or (not state.themes and not state.seed_title):
            return False
        before = len(state.queries)
        blocked = [*state.excluded, *state.queries]
        await self._expand_from_indexes(
            state.queries,
            state.index_notes,
            user_id=user_id,
            research=TitleResearchSpec(
                themes=tuple(state.themes),
                seed_title=state.seed_title,
                limit=min(_RESEARCH_POOL, max(need + 5, need)),
                exclude_titles=tuple(blocked),
            ),
        )
        excluded = {exclude_title_key(t) for t in state.excluded}
        state.queries = [
            q for q in cap_queries(state.queries) if exclude_title_key(q) not in excluded
        ]
        return len(state.queries) > before

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
        research: TitleResearchSpec,
    ) -> None:
        needs_research = bool(research.themes or research.seed_title)
        if not needs_research:
            return
        if self._llm is None:
            raise DiscoveryRecommendError(
                "Theme/seed discovery requires title research (LLM not configured)"
            )
        hits = await titles_from_research(
            self._llm,
            user_id=user_id,
            spec=research,
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

    async def _ingest_pending_queries(
        self,
        state: _RecommendState,
        *,
        target: int,
    ) -> None:
        """Search scrape sources for not-yet-ingested queries; stop on enough exact hits."""
        pending = [q for q in state.queries if exclude_title_key(q) not in state.ingested]
        exact = 0
        for start in range(0, len(pending), _SEARCH_CONCURRENCY):
            batch = pending[start : start + _SEARCH_CONCURRENCY]
            hits_by_query = await asyncio.gather(*(_safe_search(q) for q in batch))
            for query, hits in zip(batch, hits_by_query, strict=True):
                await self._apply_hits(query, hits, state.query_hits)
                state.ingested.add(exclude_title_key(query))
                if _exact_hit_for_query(query, hits):
                    exact += 1
            if exact >= target:
                break

    async def _ingest_recommend_queries(
        self,
        queries: list[str],
        *,
        target: int,
    ) -> dict[str, list[str]]:
        """Search sources (concurrency 2); upsert sequentially; early-stop on exact hits."""
        state = _RecommendState(
            queries=list(queries),
            index_notes={},
            themes=[],
            seed_title=None,
            excluded=[],
            ingested=set(),
            query_hits={},
        )
        await self._ingest_pending_queries(state, target=target)
        return state.query_hits

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
        filters: _RecommendFilters,
        limit: int,
        evidence: _RecommendEvidence,
    ) -> list[tuple[DiscoveredBook, list[str]]]:
        if filters.exclude_owned:
            books = [b for b in books if b.normalized_title not in owned]
        blocked = {exclude_title_key(t) for t in filters.exclude_titles}
        if blocked:
            books = [b for b in books if exclude_title_key(b.normalized_title) not in blocked]
        sources = await self._repo.list_sources([book.id for book in books])
        by_book: dict[UUID, list[BookSource]] = {book.id: [] for book in books}
        for src in sources:
            by_book.setdefault(src.discovered_book_id, []).append(src)
        books = [b for b in books if by_book.get(b.id)]
        books = [
            b
            for b in books
            if matches_recommend_query(b.normalized_title, queries)
            and not is_derivative_title(b.normalized_title, queries)
            and passes_source_and_chapters(
                by_book.get(b.id, []),
                source=filters.source,
                min_chapters=filters.min_chapters,
                exclude_sources=filters.exclude_sources,
            )
        ]
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
        scored = dedupe_by_exclude_key(scored)
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
            existing_source.chapter_count_estimate = better_chapter_estimate(
                existing_source.chapter_count_estimate,
                hit.chapter_count_estimate,
            )
            return
        normalized = normalize_title(hit.title)
        book = await self._repo.find_by_normalized_title(normalized)
        if book is None:
            book = await self._find_book_by_exclude_key(hit.title)
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

    async def _find_book_by_exclude_key(self, title: str) -> DiscoveredBook | None:
        """Reuse a book row when only articles/aliases differ (e.g. The Desolate Era)."""
        key = exclude_title_key(title)
        if not key:
            return None
        for candidate in (key, f"the {key}", f"a {key}"):
            found = await self._repo.find_by_normalized_title(candidate)
            if found is not None:
                return found
        return None

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


def _exact_hit_for_query(query: str, hits: list[ExternalSearchHit]) -> bool:
    """True when a source hit matches the researched query title (not a lookalike)."""
    want = exclude_title_key(query)
    return any(exclude_title_key(hit.title) == want for hit in hits)


def _ranked_source_reads(sources: list[BookSource]) -> list[BookSourceRead]:
    ranked = rank_sources(sources)
    return [
        BookSourceRead.model_validate(src).model_copy(update={"recommended": index == 0})
        for index, src in enumerate(ranked)
    ]


def _scrapable_chapters(
    book: DiscoveredBookRead,
    *,
    preferred: str | None = None,
) -> int | None:
    """Best known chapter estimate; hide thin listings that are usually incomplete TOCs."""
    best = source_chapter_estimate(book.sources, preferred=preferred)
    if best is None:
        estimates = [s.chapter_count_estimate for s in book.sources if s.chapter_count_estimate]
        best = max(estimates) if estimates else None
    if best is None or best < _MIN_RELIABLE_CHAPTER_ESTIMATE:
        return None
    return best


def _normalize_source_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip().lower()
    if not key:
        return None
    if key not in SOURCE_DOMAINS:
        known = ", ".join(sorted(SOURCE_DOMAINS))
        raise DiscoveryRecommendError(f"Unknown source '{raw}'. Supported: {known}")
    return key


def _normalize_source_names(raw: tuple[str, ...] | list[str]) -> frozenset[str]:
    out: set[str] = set()
    for item in raw:
        name = _normalize_source_name(item)
        if name is not None:
            out.add(name)
    return frozenset(out)


def better_chapter_estimate(current: int | None, incoming: int | None) -> int | None:
    """Keep the richer chapter estimate; never replace a better count with a worse one."""
    if incoming is None:
        return current
    if current is None or incoming > current:
        return incoming
    return current


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
