"""Import domain exceptions."""


class EpubImportError(Exception):
    """Base import error."""


class ImportJobNotFoundError(EpubImportError):
    """No in-memory import job for this id (or wrong owner)."""


class InvalidEpubUploadError(EpubImportError):
    """Multipart upload failed validation."""
