"""Book domain exceptions."""


class BookError(Exception):
    """Base book error."""


class BookNotFoundError(BookError):
    """Book missing or soft-deleted."""
