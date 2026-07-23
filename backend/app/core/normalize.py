"""Shared text helpers."""


def normalize_title(title: str) -> str:
    """Normalize a book title for lookup/search."""
    return " ".join(title.strip().lower().split())
