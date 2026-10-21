"""Adapter registry — resolve a URL to the matching site adapter."""

from __future__ import annotations

from app.modules.scraping.adapters.base import ScrapeAdapter
from app.modules.scraping.adapters.freewebnovel import FreewebnovelAdapter
from app.modules.scraping.adapters.novelbin import NovelbinAdapter
from app.modules.scraping.adapters.novelfire import NovelfireAdapter
from app.modules.scraping.adapters.novelfull import NovelfullAdapter
from app.modules.scraping.adapters.novellunar import NovellunarAdapter
from app.modules.scraping.adapters.ranobes import RanobesAdapter
from app.modules.scraping.adapters.scribblehub import ScribblehubAdapter
from app.modules.scraping.exceptions import UnsupportedSourceError

_ADAPTERS: list[ScrapeAdapter] = [
    NovelbinAdapter(),
    NovelfullAdapter(),
    FreewebnovelAdapter(),
    NovellunarAdapter(),
    NovelfireAdapter(),
    RanobesAdapter(),
    ScribblehubAdapter(),
]

SOURCE_DOMAINS: dict[str, list[str]] = {
    "novelbin": ["novelbin.com"],
    "novelfull": ["novelfull.net"],
    "freewebnovel": ["freewebnovel.com"],
    "novellunar": ["novellunar.com"],
    "novelfire": ["novelfire.net", "novelphoenix.com"],
    "ranobes": ["ranobes.top", "ranobes.net"],
    "scribblehub": ["scribblehub.com"],
}

ALL_ALLOWED_HOSTS: set[str] = set()
for _domains in SOURCE_DOMAINS.values():
    ALL_ALLOWED_HOSTS.update(_domains)
    for _d in _domains:
        ALL_ALLOWED_HOSTS.add(f"www.{_d}")
        ALL_ALLOWED_HOSTS.add(f"img.{_d}")
        ALL_ALLOWED_HOSTS.add(f"cdn.{_d}")

ALL_ALLOWED_HOSTS.update({"img.novellunar.com", "cdn.novelbin.com"})


def supported_source_names() -> str:
    """Comma-separated scrape/discovery source names for prompts and tool copy."""
    return ", ".join(sorted(SOURCE_DOMAINS))


def supported_sites_for_prompt() -> str:
    """Source names plus mirror-host notes for the orchestrator system prompt."""
    return (
        f"{supported_source_names()}. "
        "Novelfire mirror host novelphoenix.com is supported — treat it as novelfire "
        "and call scrape_book_range with the URL; do not refuse."
    )


def normalize_scrape_url(url: str) -> str:
    """Canonicalize mirror/alternate host URLs before fetch or job creation."""
    adapter = get_adapter(url)
    if adapter.name == "novelfire":
        from app.modules.scraping.adapters.novelfire import canonicalize_novelfire_url

        return canonicalize_novelfire_url(url)
    return url


def get_adapter(url: str) -> ScrapeAdapter:
    """Return the adapter matching *url*, or raise UnsupportedSourceError."""
    for adapter in _ADAPTERS:
        if adapter.matches(url):
            return adapter
    names = ", ".join(sorted(SOURCE_DOMAINS))
    raise UnsupportedSourceError(f"Unsupported site. Supported: {names}")


def adapter_by_name(name: str) -> ScrapeAdapter:
    """Return adapter by source name."""
    for adapter in _ADAPTERS:
        if adapter.name == name:
            return adapter
    raise UnsupportedSourceError(f"Unknown source: {name}")
