"""Structured title research for discovery recommend (via LlmService)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.normalize import normalize_title
from app.modules.discovery.exceptions import DiscoveryRecommendError
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.exceptions import LlmError
from app.modules.llm.service import LlmService
from app.modules.llm.types import Message, Role, StructuredOutputRequest

logger = logging.getLogger(__name__)

_MAX_TITLES = 10
_SYSTEM = (
    "You recommend ENGLISH-TRANSLATED web novels and light novels "
    "(xianxia, xuanhuan, wuxia, cultivation, system, isekai, KR/CN/JP web serials). "
    "Never recommend finance, history, self-help, or unrelated mainstream books. "
    "If a title is 'Against the Gods', it means the Chinese web novel 逆天邪神 "
    "(not Peter Bernstein's finance book). "
    "Prefer common English fan-translation titles readers search on NovelFull-style "
    "sites (e.g. Martial God Asura, Coiling Dragon, I Shall Seal the Heavens). "
    "Only return widely known titles you are confident exist — do not invent "
    "lookalike or nonsense titles. Return JSON only matching the schema."
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


async def titles_from_research(
    llm: LlmService,
    *,
    user_id: UUID,
    themes: list[str],
    seed_title: str | None,
    limit: int = _MAX_TITLES,
    conversation_id: UUID | None = None,
) -> list[ResearchTitleHit]:
    """Expand themes/seed via structured LLM titles (no Google Search grounding)."""
    cleaned_themes = [t.strip() for t in themes if t.strip()]
    seed = (seed_title or "").strip() or None
    if not cleaned_themes and seed is None:
        return []
    try:
        payload = await llm.generate_structured(
            _request(cleaned_themes, seed, limit=limit),
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
    return _hits_from_payload(payload, seed_title=seed, limit=limit)


def _request(
    themes: list[str],
    seed: str | None,
    *,
    limit: int,
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
    parts.append('Respond as JSON: {"titles":[{"title":"...","reason":"why similar"}]}')
    return StructuredOutputRequest(
        messages=[
            Message(role=Role.SYSTEM, content=_SYSTEM),
            Message(role=Role.USER, content="\n".join(parts)),
        ],
        response_model=_ResearchTitles,
        temperature=0.2,
        max_output_tokens=1024,
        task="discovery_research",
        use_web_search=False,
    )


def _hits_from_payload(
    payload: _ResearchTitles,
    *,
    seed_title: str | None,
    limit: int,
    note_prefix: str = "title research",
) -> list[ResearchTitleHit]:
    seed_norm = normalize_title(seed_title) if seed_title else None
    out: list[ResearchTitleHit] = []
    seen: set[str] = set()
    for row in payload.titles:
        title = " ".join(row.title.split()).strip()
        if not title:
            continue
        key = normalize_title(title)
        if not key or key in seen:
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
