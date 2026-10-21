"""Unit tests for the adapter registry."""

import pytest
from app.modules.scraping.exceptions import UnsupportedSourceError
from app.modules.scraping.registry import (
    adapter_by_name,
    get_adapter,
    normalize_scrape_url,
)

pytestmark = pytest.mark.unit


class TestGetAdapter:
    def test_novelbin(self) -> None:
        adapter = get_adapter("https://novelbin.com/b/test/chapter-1")
        assert adapter.name == "novelbin"

    def test_novelfull(self) -> None:
        adapter = get_adapter("https://novelfull.net/test/chapter-1")
        assert adapter.name == "novelfull"

    def test_freewebnovel(self) -> None:
        adapter = get_adapter("https://freewebnovel.com/novel/test/chapter-1")
        assert adapter.name == "freewebnovel"

    def test_novellunar(self) -> None:
        adapter = get_adapter("https://novellunar.com/novel/test/chapter/1")
        assert adapter.name == "novellunar"

    def test_novelfire(self) -> None:
        adapter = get_adapter("https://novelfire.net/book/test/chapter-1")
        assert adapter.name == "novelfire"

    def test_novelfire_mirror(self) -> None:
        adapter = get_adapter("https://novelphoenix.com/novel/test/chapter-1")
        assert adapter.name == "novelfire"

    def test_normalize_novelfire_mirror(self) -> None:
        raw = "https://novelphoenix.com/novel/hell-difficulty-tutorial/chapter-1"
        assert normalize_scrape_url(raw) == (
            "https://novelfire.net/book/hell-difficulty-tutorial/chapter-1"
        )

    def test_ranobes(self) -> None:
        adapter = get_adapter("https://ranobes.top/novels/1-test.html")
        assert adapter.name == "ranobes"

    def test_scribblehub(self) -> None:
        adapter = get_adapter("https://www.scribblehub.com/series/1/test/")
        assert adapter.name == "scribblehub"

    def test_unsupported_raises(self) -> None:
        with pytest.raises(UnsupportedSourceError):
            get_adapter("https://unknown-site.com/novel")


class TestAdapterByName:
    def test_known_name(self) -> None:
        adapter = adapter_by_name("novelbin")
        assert adapter.name == "novelbin"

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(UnsupportedSourceError):
            adapter_by_name("nonexistent")
