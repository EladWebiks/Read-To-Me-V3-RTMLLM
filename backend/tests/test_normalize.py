"""Unit tests for title normalization."""

import pytest
from app.core.normalize import normalize_title


@pytest.mark.unit
def test_normalize_title_collapses_whitespace() -> None:
    """Titles are lowercased and whitespace-normalized."""
    assert normalize_title("  Hello   World ") == "hello world"
