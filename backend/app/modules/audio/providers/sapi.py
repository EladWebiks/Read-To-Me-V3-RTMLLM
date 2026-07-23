"""SAPI facade: local Windows first, HTTP proxy fallback."""

from __future__ import annotations

from app.core.config import get_settings
from app.modules.audio.providers.base import VoiceInfo
from app.modules.audio.providers.sapi_local import DEFAULT_SAPI_VOICE, LocalSapiProvider
from app.modules.audio.providers.sapi_proxy import SapiProxyProvider


class SapiTtsProvider:
    """Prefer local Zira/SAPI; fall back to proxy off Windows."""

    def __init__(
        self,
        local: LocalSapiProvider | None = None,
        proxy: SapiProxyProvider | None = None,
    ) -> None:
        self._local = local or LocalSapiProvider()
        self._proxy = proxy or SapiProxyProvider()

    @property
    def name(self) -> str:
        return "sapi"

    async def list_voices(self) -> list[VoiceInfo]:
        if self._local.is_available():
            voices = await self._local.list_voices()
            if voices:
                return voices
        if get_settings().sapi_proxy_enabled:
            return await self._proxy.list_voices()
        return [
            VoiceInfo(
                provider=self.name,
                id=DEFAULT_SAPI_VOICE,
                name=DEFAULT_SAPI_VOICE,
                locale="en-US",
            )
        ]

    async def synthesize(self, text: str, voice: str, rate: float) -> bytes:
        if self._local.is_available():
            try:
                return await self._local.synthesize(text, voice, rate)
            except Exception:
                if not get_settings().sapi_proxy_enabled:
                    raise
        if not get_settings().sapi_proxy_enabled:
            raise RuntimeError("SAPI unavailable (not Windows and proxy disabled)")
        return await self._proxy.synthesize(text, voice, rate)
