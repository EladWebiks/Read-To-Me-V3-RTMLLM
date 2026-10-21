"""SSRF-safe HTTP fetcher for scraping."""

from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}  # noqa: S104
_MIN_CHAPTER_HTML_BYTES = 8000
_CF_BLOCK_MARKERS = (
    "challenge-platform",
    "cf-browser-verification",
    "cdn-cgi/challenge",
    "__cf$cv$params",
    "just a moment",
    "checking your browser",
    "attention required",
)


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


def looks_like_bot_block(html: str) -> bool:
    """Heuristic for Cloudflare / anti-bot interstitials (not real chapter HTML).

    Real NovelFire pages embed ``challenge-platform`` / ``cdn-cgi`` scripts even
    when ``div#content`` is present — markers alone are not enough. Only short
    responses that also look like a CF interstitial count as blocked.
    """
    if len(html) >= _MIN_CHAPTER_HTML_BYTES:
        return False
    lowered = html.lower()
    if any(marker in lowered for marker in _CF_BLOCK_MARKERS):
        return True
    return "cloudflare" in lowered


def _decode_response(resp: httpx.Response, max_bytes: int) -> str:
    raw = resp.content[:max_bytes]
    return raw.decode(resp.encoding or "utf-8", errors="replace")


class FetchSession:
    """Reuses one HTTP client (cookies + connections) for a scrape walk."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> FetchSession:
        await self._open()
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self._close()

    async def reset(self) -> None:
        """Drop a poisoned connection pool (e.g. after NovelFire disconnects)."""
        await self._close()
        await self._open()

    async def _open(self) -> None:
        settings = get_settings()
        self._client = httpx.AsyncClient(
            timeout=settings.scrape.timeout_seconds,
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": _USER_AGENT},
        )

    async def _close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_html(
        self,
        url: str,
        allowlist: set[str],
        *,
        headers: dict[str, str] | None = None,
    ) -> str:
        validate_url(url, allowlist)
        if self._client is None:
            raise FetchError("FetchSession is not active")
        settings = get_settings()
        try:
            resp = await self._client.get(url, headers=headers or {})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc
        return _decode_response(resp, settings.scrape.max_bytes)

    async def fetch_bytes(self, url: str, allowlist: set[str]) -> bytes:
        validate_url(url, allowlist)
        if self._client is None:
            raise FetchError("FetchSession is not active")
        settings = get_settings()
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc
        return resp.content[: settings.scrape.max_bytes]


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
        return _decode_response(resp, settings.scrape.max_bytes)


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


async def get_json(
    url: str,
    allowlist: set[str],
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    """GET JSON and return a parsed object (SSRF-safe)."""
    return await _request_json("GET", url, allowlist, headers=headers)


async def post_json(
    url: str,
    allowlist: set[str],
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    """POST JSON body and return parsed object (SSRF-safe)."""
    return await _request_json("POST", url, allowlist, headers=headers, json_body=payload)


async def _request_json(
    method: str,
    url: str,
    allowlist: set[str],
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, object] | None = None,
) -> dict[str, object]:
    validate_url(url, allowlist)
    settings = get_settings()
    req_headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
        **(headers or {}),
    }
    if json_body is not None:
        req_headers.setdefault("Content-Type", "application/json")
    async with httpx.AsyncClient(
        timeout=settings.scrape.timeout_seconds,
        follow_redirects=True,
        max_redirects=5,
        headers=req_headers,
    ) as client:
        resp = await client.request(method, url, json=json_body)
        resp.raise_for_status()
        raw = resp.content[: settings.scrape.max_bytes]
        try:
            data: object = json.loads(raw.decode(resp.encoding or "utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise FetchError("Invalid JSON response") from exc
        if not isinstance(data, dict):
            raise FetchError("JSON response was not an object")
        return data


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
