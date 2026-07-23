"""Chapter domain exceptions."""


class ChapterError(Exception):
    """Base chapter error."""


class ChapterNotFoundError(ChapterError):
    """Chapter missing or soft-deleted."""


class ChapterNumberConflictError(ChapterError):
    """Chapter number already used for this book."""
