"""Shared fixtures for scraping adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "scraping"


def _fixture(site: str, name: str) -> str:
    return (FIXTURE_DIR / site / name).read_text(encoding="utf-8")


@pytest.fixture
def novelbin_book_html() -> str:
    return _fixture("novelbin", "book.html")


@pytest.fixture
def novelbin_chapter_html() -> str:
    return _fixture("novelbin", "chapter.html")


@pytest.fixture
def novelfull_book_html() -> str:
    return _fixture("novelfull", "book.html")


@pytest.fixture
def novelfull_chapter_html() -> str:
    return _fixture("novelfull", "chapter.html")


@pytest.fixture
def freewebnovel_book_html() -> str:
    return _fixture("freewebnovel", "book.html")


@pytest.fixture
def freewebnovel_chapter_html() -> str:
    return _fixture("freewebnovel", "chapter.html")


@pytest.fixture
def novellunar_book_html() -> str:
    return _fixture("novellunar", "book.html")


@pytest.fixture
def novellunar_chapter_html() -> str:
    return _fixture("novellunar", "chapter.html")


@pytest.fixture
def novelfire_book_html() -> str:
    return _fixture("novelfire", "book.html")


@pytest.fixture
def novelfire_chapter_html() -> str:
    return _fixture("novelfire", "chapter.html")


@pytest.fixture
def ranobes_book_html() -> str:
    return _fixture("ranobes", "book.html")


@pytest.fixture
def ranobes_chapter_html() -> str:
    return _fixture("ranobes", "chapter.html")


@pytest.fixture
def scribblehub_book_html() -> str:
    return _fixture("scribblehub", "book.html")


@pytest.fixture
def scribblehub_chapter_html() -> str:
    return _fixture("scribblehub", "chapter.html")
