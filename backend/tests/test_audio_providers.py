"""Unit tests for audio helpers and SAPI facade."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.modules.audio.providers.base import VoiceInfo
from app.modules.audio.providers.edge import _edge_rate
from app.modules.audio.providers.sapi import SapiTtsProvider
from app.modules.audio.providers.sapi_local import LocalSapiProvider

from tests.factories import make_settings


@pytest.mark.unit
def test_edge_rate_formatting() -> None:
    assert _edge_rate(1.0) == "+0%"
    assert _edge_rate(1.25) == "+25%"
    assert _edge_rate(0.5) == "-50%"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sapi_prefers_local_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local = MagicMock(spec=LocalSapiProvider)
    local.is_available.return_value = True
    local.synthesize = AsyncMock(return_value=b"local-mp3")
    proxy = MagicMock()
    proxy.synthesize = AsyncMock(return_value=b"proxy-mp3")
    monkeypatch.setattr(
        "app.modules.audio.providers.sapi.get_settings",
        lambda: make_settings(sapi_proxy_enabled=True),
    )
    provider = SapiTtsProvider(local=local, proxy=proxy)
    result = await provider.synthesize("hello", "Microsoft Zira Desktop", 1.0)
    assert result == b"local-mp3"
    proxy.synthesize.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sapi_falls_back_to_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local = MagicMock(spec=LocalSapiProvider)
    local.is_available.return_value = False
    proxy = MagicMock()
    proxy.synthesize = AsyncMock(return_value=b"proxy-mp3")
    proxy.list_voices = AsyncMock(
        return_value=[
            VoiceInfo(provider="sapi", id="Microsoft Zira Desktop", name="Zira"),
        ]
    )
    monkeypatch.setattr(
        "app.modules.audio.providers.sapi.get_settings",
        lambda: make_settings(sapi_proxy_enabled=True),
    )
    provider = SapiTtsProvider(local=local, proxy=proxy)
    result = await provider.synthesize("hello", "Microsoft Zira Desktop", 1.0)
    assert result == b"proxy-mp3"
