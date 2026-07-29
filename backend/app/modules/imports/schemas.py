"""EPUB import DTOs (match v2 ImportProgress shape + chunked upload)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EpubImportFileSummary(BaseModel):
    """Per-file chapter count in a completed import."""

    name: str
    chapters: int


class EpubImportResult(BaseModel):
    """Final result when status is completed."""

    book_id: str
    book_title: str
    author: str
    chapters_imported: int
    files: list[EpubImportFileSummary]
    starting_chapter: int


class ImportProgress(BaseModel):
    """Progress snapshot for a running or finished EPUB import."""

    job_id: str
    status: str = Field(description="running | completed | failed | cancelled")
    chapters_imported: int = 0
    total_chapters: int | None = None
    files_total: int = 0
    files_parsed: int = 0
    current_file: str = ""
    book_title: str = ""
    message: str = ""
    result: EpubImportResult | None = None


class EpubUploadPrepare(BaseModel):
    """Start a chunked upload for one EPUB file."""

    filename: str = Field(min_length=1, max_length=512)
    size: int = Field(ge=1, le=80 * 1024 * 1024)


class EpubUploadPrepared(BaseModel):
    """Client uses chunk_size + total_chunks to PUT bytes."""

    upload_id: str
    filename: str
    size: int
    chunk_size: int
    total_chunks: int


class EpubChunkAccepted(BaseModel):
    upload_id: str
    index: int
    received_chunks: int
    total_chunks: int


class EpubUploadComplete(BaseModel):
    upload_id: str
    filename: str
    size: int


class EpubImportStart(BaseModel):
    """Start import after all chunked uploads completed."""

    upload_ids: list[str] = Field(min_length=1, max_length=20)
    title: str | None = None
    author: str | None = None
    starting_chapter: int = Field(default=1, ge=1)
