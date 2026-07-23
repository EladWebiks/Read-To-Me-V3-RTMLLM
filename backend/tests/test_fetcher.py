"""Unit tests for SSRF fetcher validation (no network)."""

import pytest
from app.core.fetcher import FetchError, validate_url


@pytest.mark.unit
def test_blocks_private_host() -> None:
    with pytest.raises(FetchError):
        validate_url("http://127.0.0.1/x", {"example.com"})


@pytest.mark.unit
def test_blocks_non_allowlisted() -> None:
    with pytest.raises(FetchError):
        validate_url("https://evil.example/x", {"novelbin.com"})


@pytest.mark.unit
def test_allows_listed_domain() -> None:
    validate_url("https://www.novelbin.com/b/foo", {"novelbin.com"})
