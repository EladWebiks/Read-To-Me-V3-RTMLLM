"""Reader domain exceptions."""


class ReaderError(Exception):
    """Base reader error."""


class ProgressNotFoundError(ReaderError):
    """No reading progress for this user/book."""
