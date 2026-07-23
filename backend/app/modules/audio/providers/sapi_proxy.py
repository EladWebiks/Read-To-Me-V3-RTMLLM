"""HTTP SAPI proxy (texttospeechfree.io) for non-Windows hosts."""

from __future__ import annotations

import re
from time import monotonic

import httpx

from app.modules.audio.providers.base import VoiceInfo
from app.modules.audio.providers.sapi_local import DEFAULT_SAPI_VOICE

BASE_URL = "https://texttospeechfree.io"
SESSION_TTL_S = 30 * 60
PROXY_VOICES = (
    "Microsoft Zira Desktop",
    "Microsoft David Desktop",
    "Microsoft Mark",
)


class SapiProxyProvider:
    """Best-effort SAPI voices via third-party proxy (v2 parity)."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._created_at = 0.0
        self._cookies: httpx.Cookies = httpx.Cookies()

    @property
    def name(self) -> str:
        return "sapi"

    async def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(provider=self.name, id=voice, name=voice, locale="en-US")
            for voice in PROXY_VOICES
        ]

    async def synthesize(self, text: str, voice: str, rate: float) -> bytes:
        async with httpx.AsyncClient(
            timeout=120.0,
            follow_redirects=True,
            cookies=self._cookies,
        ) as client:
            await self._ensure_session(client)
            try:
                return await self._synthesize_once(client, text, voice, rate)
            except (httpx.HTTPStatusError, RuntimeError):
                await self._ensure_session(client, force=True)
                return await self._synthesize_once(client, text, voice, rate)

    async def _ensure_session(
        self,
        client: httpx.AsyncClient,
        *,
        force: bool = False,
    ) -> None:
        fresh = monotonic() - self._created_at < SESSION_TTL_S
        if not force and self._token and fresh:
            return
        response = await client.get(f"{BASE_URL}/")
        response.raise_for_status()
        match = re.search(
            r'name="__RequestVerificationToken".*?value="([^"]+)"',
            response.text,
        )
        if match is None:
            raise RuntimeError("SAPI proxy: XSRF token missing")
        self._token = match.group(1)
        self._cookies = httpx.Cookies(client.cookies)
        self._created_at = monotonic()

    async def _synthesize_once(
        self,
        client: httpx.AsyncClient,
        text: str,
        voice: str,
        rate: float,
    ) -> bytes:
        token = self._token
        if token is None:
            raise RuntimeError("SAPI proxy: session not initialized")
        create = await client.post(
            f"{BASE_URL}/Index?handler=Test",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "XSRF-TOKEN": token,
            },
            json={
                "Text": text,
                "Voice": voice or DEFAULT_SAPI_VOICE,
                "Rate": _site_rate(rate),
                "Volume": "100",
            },
        )
        create.raise_for_status()
        payload = create.json()
        if payload.get("isError"):
            raise RuntimeError(str(payload.get("errorMessage") or "SAPI proxy error"))
        file_id = str(payload.get("id", ""))
        file_name = str(payload.get("file", ""))
        if not file_id or not file_name:
            raise RuntimeError("SAPI proxy: empty synthesis response")
        download = await client.get(
            f"{BASE_URL}/Index?handler=Download&id={file_id}&file={file_name}",
        )
        download.raise_for_status()
        if not download.content:
            raise RuntimeError("SAPI proxy: empty audio")
        return download.content


def _site_rate(rate: float) -> str:
    clamped = max(0.5, min(2.0, rate))
    if clamped <= 1:
        return str(round((clamped - 1) * 20))
    return str(round((clamped - 1) * 10))
