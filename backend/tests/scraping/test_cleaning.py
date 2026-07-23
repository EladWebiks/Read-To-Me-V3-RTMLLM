"""Unit tests for content cleaning."""

import pytest
from app.modules.scraping.cleaning import clean_content

pytestmark = pytest.mark.unit


class TestCleanContent:
    def test_strips_ad_lines(self) -> None:
        raw = (
            "Real paragraph.\n\n"
            "If you find this story on Amazon, please report it.\n\n"
            "Another real paragraph."
        )
        result = clean_content(raw)
        assert "Real paragraph." in result
        assert "Another real paragraph." in result
        assert "Amazon" not in result

    def test_collapses_whitespace(self) -> None:
        raw = "Line one.\n\n\n\n\nLine two."
        result = clean_content(raw)
        assert result == "Line one.\n\nLine two."

    def test_preserves_normal_content(self) -> None:
        raw = "First paragraph.\n\nSecond paragraph."
        assert clean_content(raw) == raw

    def test_strips_surrounding_whitespace(self) -> None:
        raw = "   \n\nContent here.\n\n   "
        result = clean_content(raw)
        assert result == "Content here."
