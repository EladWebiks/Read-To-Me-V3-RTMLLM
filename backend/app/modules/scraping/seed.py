"""Seed default scraping sources."""

from __future__ import annotations

from typing import TypedDict

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.scraping.models import ScrapingSource


class _SourceSeed(TypedDict):
    name: str
    base_domains: list[str]
    terms_note: str


_DEFAULTS: list[_SourceSeed] = [
    {
        "name": "novelbin",
        "base_domains": ["novelbin.com"],
        "terms_note": "Honor novelbin robots/ToS; personal use only.",
    },
    {
        "name": "novelfull",
        "base_domains": ["novelfull.net"],
        "terms_note": "Honor novelfull robots/ToS; personal use only.",
    },
    {
        "name": "freewebnovel",
        "base_domains": ["freewebnovel.com"],
        "terms_note": "Honor freewebnovel robots/ToS; personal use only.",
    },
    {
        "name": "novellunar",
        "base_domains": ["novellunar.com"],
        "terms_note": "Honor novellunar robots/ToS; personal use only.",
    },
]


async def seed_scraping_sources() -> None:
    """Insert enabled sources if missing."""
    async with SessionLocal() as session:
        for item in _DEFAULTS:
            existing = await session.execute(
                select(ScrapingSource).where(ScrapingSource.name == item["name"])
            )
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(
                ScrapingSource(
                    name=item["name"],
                    base_domains=item["base_domains"],
                    enabled=True,
                    rate_limit_seconds=1.5,
                    terms_note=item["terms_note"],
                )
            )
        await session.commit()
