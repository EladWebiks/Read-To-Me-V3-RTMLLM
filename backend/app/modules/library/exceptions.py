"""Library domain exceptions."""


class LibraryError(Exception):
    """Base library error."""


class BookAccessDeniedError(LibraryError):
    """User does not own / belong to this book."""
