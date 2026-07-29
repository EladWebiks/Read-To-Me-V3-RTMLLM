"""Temp-file staging for chunked EPUB uploads."""

from __future__ import annotations

import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from app.modules.imports.exceptions import InvalidEpubUploadError

_CHUNK_BYTES = 512 * 1024  # 512 KiB — stays under typical 1MB proxy caps
_MAX_BYTES = 80 * 1024 * 1024
_MAX_FILES = 20
_TTL_SECONDS = 3600
_lock = threading.Lock()
_uploads: dict[str, UploadSession] = {}


@dataclass
class UploadSession:
    upload_id: str
    user_id: str
    filename: str
    size: int
    total_chunks: int
    path: Path
    received: set[int] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    completed: bool = False


def chunk_size_bytes() -> int:
    return _CHUNK_BYTES


def max_file_bytes() -> int:
    return _MAX_BYTES


def prepare_upload(user_id: UUID, filename: str, size: int) -> UploadSession:
    """Create a staging file for chunked upload."""
    _purge_stale()
    if not filename.lower().endswith(".epub"):
        raise InvalidEpubUploadError(f"Invalid file type: {filename} (expected .epub)")
    if size <= 0:
        raise InvalidEpubUploadError(f"Empty file: {filename}")
    if size > _MAX_BYTES:
        raise InvalidEpubUploadError(f"File too large: {filename} (max 80MB)")
    total_chunks = max(1, (size + _CHUNK_BYTES - 1) // _CHUNK_BYTES)
    upload_id = uuid.uuid4().hex[:16]
    path = Path(tempfile.gettempdir()) / f"rtm-epub-{upload_id}.part"
    path.touch()
    session = UploadSession(
        upload_id=upload_id,
        user_id=str(user_id),
        filename=filename,
        size=size,
        total_chunks=total_chunks,
        path=path,
    )
    with _lock:
        _uploads[upload_id] = session
    return session


def write_chunk(user_id: UUID, upload_id: str, index: int, data: bytes) -> UploadSession:
    """Write one chunk at the expected offset."""
    session = _require(user_id, upload_id)
    if session.completed:
        raise InvalidEpubUploadError("Upload already completed")
    if index < 0 or index >= session.total_chunks:
        raise InvalidEpubUploadError(f"Invalid chunk index {index}")
    offset = index * _CHUNK_BYTES
    expected = min(_CHUNK_BYTES, session.size - offset)
    if len(data) != expected:
        raise InvalidEpubUploadError(
            f"Chunk {index} size mismatch (got {len(data)}, expected {expected})"
        )
    with session.path.open("r+b") as handle:
        handle.seek(offset)
        handle.write(data)
    session.received.add(index)
    return session


def complete_upload(user_id: UUID, upload_id: str) -> UploadSession:
    """Mark upload complete once all chunks arrived."""
    session = _require(user_id, upload_id)
    if len(session.received) != session.total_chunks:
        missing = session.total_chunks - len(session.received)
        raise InvalidEpubUploadError(f"Upload incomplete ({missing} chunk(s) missing)")
    session.completed = True
    return session


def take_payloads(user_id: UUID, upload_ids: list[str]) -> list[tuple[str, bytes]]:
    """Read completed uploads and remove staging files."""
    if not upload_ids:
        raise InvalidEpubUploadError("At least one EPUB upload is required")
    if len(upload_ids) > _MAX_FILES:
        raise InvalidEpubUploadError(f"Too many files (max {_MAX_FILES})")
    payloads: list[tuple[str, bytes]] = []
    for upload_id in upload_ids:
        session = _require(user_id, upload_id)
        if not session.completed:
            raise InvalidEpubUploadError(f"Upload not completed: {session.filename}")
        data = session.path.read_bytes()
        payloads.append((session.filename, data))
        _remove(upload_id)
    return payloads


def _require(user_id: UUID, upload_id: str) -> UploadSession:
    with _lock:
        session = _uploads.get(upload_id)
    if session is None or session.user_id != str(user_id):
        raise InvalidEpubUploadError("Upload not found")
    return session


def _remove(upload_id: str) -> None:
    with _lock:
        session = _uploads.pop(upload_id, None)
    if session is not None:
        session.path.unlink(missing_ok=True)


def _purge_stale() -> None:
    now = time.time()
    with _lock:
        stale = [uid for uid, sess in _uploads.items() if now - sess.created_at > _TTL_SECONDS]
    for uid in stale:
        _remove(uid)
