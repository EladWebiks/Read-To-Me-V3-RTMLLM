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
    rate_limit_seconds: float


_DEFAULTS: list[_SourceSeed] = [
    {
        "name": "novelbin",
        "base_domains": ["novelbin.com"],
        "terms_note": "Honor novelbin robots/ToS; personal use only.",
        "rate_limit_seconds": 1.5,
    },
    {
        "name": "novelfull",
        "base_domains": ["novelfull.net"],
        "terms_note": "Honor novelfull robots/ToS; personal use only.",
        "rate_limit_seconds": 1.5,
    },
    {
        "name": "freewebnovel",
        "base_domains": ["freewebnovel.com"],
        "terms_note": "Honor freewebnovel robots/ToS; personal use only.",
        "rate_limit_seconds": 1.5,
    },
    {
        "name": "novellunar",
        "base_domains": ["novellunar.com"],
        "terms_note": "Honor novellunar robots/ToS; personal use only.",
        "rate_limit_seconds": 1.5,
    },
    {
        "name": "novelfire",
        "base_domains": ["novelfire.net"],
        "terms_note": "Honor novelfire robots/ToS; personal use only. Cloudflare-fronted.",
        "rate_limit_seconds": 3.0,
    },
    {
        "name": "ranobes",
        "base_domains": ["ranobes.top", "ranobes.net"],
        "terms_note": "Honor ranobes robots/ToS; personal use only. Aggressive anti-flood.",
        "rate_limit_seconds": 5.0,
    },
    {
        "name": "scribblehub",
        "base_domains": ["scribblehub.com"],
        "terms_note": "Honor ScribbleHub robots/ToS; personal use only. Cloudflare-fronted.",
        "rate_limit_seconds": 2.0,
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
                    rate_limit_seconds=item["rate_limit_seconds"],
                    terms_note=item["terms_note"],
                )
            )
        await session.commit()
