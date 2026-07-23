"""Shared fixtures for scraping adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "scraping"


@pytest.fixture
def novelbin_book_html() -> str:
    return (FIXTURE_DIR / "novelbin" / "book.html").read_text()


@pytest.fixture
def novelbin_chapter_html() -> str:
    return (FIXTURE_DIR / "novelbin" / "chapter.html").read_text()


@pytest.fixture
def novelfull_book_html() -> str:
    return (FIXTURE_DIR / "novelfull" / "book.html").read_text()


@pytest.fixture
def novelfull_chapter_html() -> str:
    return (FIXTURE_DIR / "novelfull" / "chapter.html").read_text()


@pytest.fixture
def freewebnovel_book_html() -> str:
    return (FIXTURE_DIR / "freewebnovel" / "book.html").read_text()


@pytest.fixture
def freewebnovel_chapter_html() -> str:
    return (FIXTURE_DIR / "freewebnovel" / "chapter.html").read_text()


@pytest.fixture
def novellunar_book_html() -> str:
    return (FIXTURE_DIR / "novellunar" / "book.html").read_text()


@pytest.fixture
def novellunar_chapter_html() -> str:
    return (FIXTURE_DIR / "novellunar" / "chapter.html").read_text()
