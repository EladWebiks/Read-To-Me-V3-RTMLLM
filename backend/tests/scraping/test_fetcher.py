"""Unit tests for SSRF-safe fetcher — no network calls."""

import pytest
from app.core.fetcher import FetchError, validate_url

pytestmark = pytest.mark.unit

ALLOW = {"novelbin.com", "novelfull.net"}


class TestAllowlist:
    def test_allowed_domain(self) -> None:
        validate_url("https://novelbin.com/b/some-novel", ALLOW)

    def test_allowed_subdomain(self) -> None:
        validate_url("https://www.novelbin.com/b/some-novel", ALLOW)

    def test_rejected_domain(self) -> None:
        with pytest.raises(FetchError, match="not in allowlist"):
            validate_url("https://evil.com/page", ALLOW)

    def test_rejected_empty_allowlist(self) -> None:
        with pytest.raises(FetchError, match="not in allowlist"):
            validate_url("https://novelbin.com/b/test", set())


class TestScheme:
    def test_rejects_ftp(self) -> None:
        with pytest.raises(FetchError, match="Scheme"):
            validate_url("ftp://novelbin.com/file", ALLOW)

    def test_rejects_file(self) -> None:
        with pytest.raises(FetchError, match="Scheme"):
            validate_url("file:///etc/passwd", ALLOW)


class TestPrivateIP:
    def test_rejects_localhost(self) -> None:
        with pytest.raises(FetchError):
            validate_url("http://localhost/admin", {"localhost"})

    def test_rejects_127(self) -> None:
        with pytest.raises(FetchError):
            validate_url("http://127.0.0.1/admin", {"127.0.0.1"})


class TestNoHost:
    def test_rejects_no_host(self) -> None:
        with pytest.raises(FetchError, match="No host"):
            validate_url("https://", ALLOW)
