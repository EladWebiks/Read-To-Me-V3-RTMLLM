"""Download job domain exceptions."""


class DownloadJobNotFoundError(Exception):
    """Download job missing or not owned."""


class DownloadNotReadyError(Exception):
    """Signed URL requested before job completed."""


class InvalidChapterRangeError(Exception):
    """Chapter range is empty or inverted."""
