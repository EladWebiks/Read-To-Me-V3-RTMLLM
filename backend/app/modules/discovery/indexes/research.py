"""Structured title research for discovery recommend (via LlmService)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.discovery.exceptions import DiscoveryRecommendError
from app.modules.discovery.recommend import exclude_title_key
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.exceptions import LlmError
from app.modules.llm.service import LlmService
from app.modules.llm.types import Message, Role, StructuredOutputRequest

logger = logging.getLogger(__name__)

_MAX_TITLES = 25
_SYSTEM = (
    "You recommend ENGLISH-TRANSLATED web novels and light novels "
    "(xianxia, xuanhuan, wuxia, cultivation, system, isekai, KR/CN/JP web serials). "
    "Never recommend finance, history, self-help, or unrelated mainstream books. "
    "If a title is 'Against the Gods', it means the Chinese web novel 逆天邪神 "
    "(not Peter Bernstein's finance book). "
    "Prefer common English fan-translation titles readers search on NovelFull-style "
    "sites (e.g. Martial God Asura, Coiling Dragon, I Shall Seal the Heavens). "
    "Treat well-known alternate titles as the same book (e.g. Master of Gu = "
    "Reverend Insanity; Xian Ni = Renegade Immortal) — do not recommend an alias "
    "of an excluded or seed title. "
    "Never recommend fanfiction, spinoffs, 'system' clones, or titles that extend a "
    "famous series with a colon/dash subtitle (e.g. 'Martial Peak - Rise of…', "
    "'Desolate Era: Hatching…'). Prefer the original main series only. "
    "Only return widely known titles you are confident exist — do not invent "
    "lookalike or nonsense titles. For each title, reason must be a one-sentence "
    "no-spoiler premise (setting + hook), not just 'similar cultivation'. "
    "Return JSON only matching the schema."
)


class _ResearchTitle(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(default="", max_length=300)


class _ResearchTitles(BaseModel):
    titles: list[_ResearchTitle] = Field(default_factory=list, max_length=_MAX_TITLES)


@dataclass(frozen=True, slots=True)
class ResearchTitleHit:
    """One title proposed by structured LLM research."""

    title: str
    note: str


@dataclass(frozen=True, slots=True)
class TitleResearchSpec:
    """Inputs for theme/seed title expansion."""

    themes: tuple[str, ...]
    seed_title: str | None
    limit: int = _MAX_TITLES
    exclude_titles: tuple[str, ...] = ()


async def titles_from_research(
    llm: LlmService,
    *,
    user_id: UUID,
    spec: TitleResearchSpec,
    conversation_id: UUID | None = None,
) -> list[ResearchTitleHit]:
    """Expand themes/seed via structured LLM titles (no Google Search grounding)."""
    cleaned_themes = [t.strip() for t in spec.themes if t.strip()]
    seed = (spec.seed_title or "").strip() or None
    if not cleaned_themes and seed is None:
        return []
    # Theme/seed research: always pull a full pool so site filtering can still fill limit.
    want = max(spec.limit, _MAX_TITLES if (cleaned_themes or seed) else spec.limit)
    capped = max(1, min(want, _MAX_TITLES))
    excluded = [t.strip() for t in spec.exclude_titles if t.strip()]
    try:
        payload = await llm.generate_structured(
            _request(cleaned_themes, seed, limit=capped, exclude_titles=excluded),
            user_id=user_id,
            capability=ModelCapability.STRUCTURED_EXTRACTION,
            conversation_id=conversation_id,
        )
    except LlmError as exc:
        logger.warning("discovery title research failed: %s", exc)
        raise DiscoveryRecommendError(f"Title research failed: {exc}") from exc
    except Exception as exc:
        logger.warning("discovery title research failed: %s", exc)
        raise DiscoveryRecommendError(f"Title research failed: {exc}") from exc
    return _hits_from_payload(
        payload,
        seed_title=seed,
        limit=capped,
        exclude_titles=excluded,
    )


def _request(
    themes: list[str],
    seed: str | None,
    *,
    limit: int,
    exclude_titles: list[str],
) -> StructuredOutputRequest[_ResearchTitles]:
    parts = [
        f"Recommend up to {limit} DISTINCT English-translated web novels.",
        "Exclude the seed title itself. Do not invent lookalike titles of the seed.",
        "Use common English fan-translation titles found on NovelFull-style sites.",
    ]
    if seed:
        parts.append(f"Seed web novel: {seed}")
    if themes:
        parts.append("Themes/tropes: " + ", ".join(themes))
    if exclude_titles:
        sample = ", ".join(exclude_titles[:40])
        parts.append(f"Do NOT include these already-suggested titles: {sample}")
    parts.append(
        'Respond as JSON: {"titles":[{"title":"...","reason":"one-sentence no-spoiler premise"}]}'
    )
    return StructuredOutputRequest(
        messages=[
            Message(role=Role.SYSTEM, content=_SYSTEM),
            Message(role=Role.USER, content="\n".join(parts)),
        ],
        response_model=_ResearchTitles,
        temperature=0.2,
        max_output_tokens=2048,
        task="discovery_research",
        use_web_search=False,
    )


def _hits_from_payload(
    payload: _ResearchTitles,
    *,
    seed_title: str | None,
    limit: int,
    exclude_titles: list[str] | None = None,
    note_prefix: str = "title research",
) -> list[ResearchTitleHit]:
    seed_norm = exclude_title_key(seed_title) if seed_title else None
    excluded = {exclude_title_key(t) for t in (exclude_titles or []) if t.strip()}
    out: list[ResearchTitleHit] = []
    seen: set[str] = set()
    for row in payload.titles:
        title = " ".join(row.title.split()).strip()
        if not title:
            continue
        key = exclude_title_key(title)
        if not key or key in seen or key in excluded:
            continue
        if seed_norm is not None and key == seed_norm:
            continue
        seen.add(key)
        reason = " ".join(row.reason.split()).strip()
        note = f"{note_prefix}: {reason}" if reason else note_prefix
        out.append(ResearchTitleHit(title=title, note=note))
        if len(out) >= limit:
            break
    return out
