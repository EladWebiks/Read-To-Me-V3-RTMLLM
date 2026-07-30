"""SSRF-safe HTTP fetcher for scraping."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}  # noqa: S104


class FetchError(Exception):
    """Raised when a fetch is rejected or fails."""


def _is_blocked_host(host: str) -> bool:
    """Block literal private IPs and well-known local hostnames."""
    if host in _BLOCKED_HOSTS:
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def _host_allowed(url: str, allowlist: set[str]) -> bool:
    """Check the URL host against an explicit domain allowlist."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return any(host == a or host.endswith(f".{a}") for a in allowlist)


def validate_url(url: str, allowlist: set[str]) -> None:
    """Raise FetchError if URL is disallowed."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError(f"Scheme not allowed: {parsed.scheme}")
    host = parsed.hostname or ""
    if not host:
        raise FetchError("No host in URL")
    if not _host_allowed(url, allowlist):
        raise FetchError(f"Host not in allowlist: {host}")
    if _is_blocked_host(host):
        raise FetchError(f"Private/loopback IP blocked: {host}")


async def fetch_html(
    url: str,
    allowlist: set[str],
    *,
    headers: dict[str, str] | None = None,
) -> str:
    """Fetch *url* and return the response text, enforcing SSRF protections."""
    validate_url(url, allowlist)
    settings = get_settings()
    req_headers = {"User-Agent": _USER_AGENT, **(headers or {})}
    async with httpx.AsyncClient(
        timeout=settings.scrape.timeout_seconds,
        follow_redirects=True,
        max_redirects=5,
        headers=req_headers,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        raw = resp.content[: settings.scrape.max_bytes]
        return raw.decode(resp.encoding or "utf-8", errors="replace")


async def post_form_html(
    url: str,
    allowlist: set[str],
    form: dict[str, str],
    *,
    headers: dict[str, str] | None = None,
) -> str:
    """POST form-urlencoded body and return response text (SSRF-safe)."""
    validate_url(url, allowlist)
    settings = get_settings()
    req_headers = {"User-Agent": _USER_AGENT, **(headers or {})}
    async with httpx.AsyncClient(
        timeout=settings.scrape.timeout_seconds,
        follow_redirects=True,
        max_redirects=5,
        headers=req_headers,
    ) as client:
        resp = await client.post(url, data=form)
        resp.raise_for_status()
        raw = resp.content[: settings.scrape.max_bytes]
        return raw.decode(resp.encoding or "utf-8", errors="replace")


async def fetch_bytes(url: str, allowlist: set[str]) -> bytes:
    """Fetch *url* and return raw bytes (for cover images)."""
    validate_url(url, allowlist)
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.scrape.timeout_seconds,
        follow_redirects=True,
        max_redirects=5,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content[: settings.scrape.max_bytes]
