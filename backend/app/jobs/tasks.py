"""Download job worker task."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.ffmpeg import concat_mp3
from app.core.storage import put_bytes
from app.modules.audio.providers import get_provider
from app.modules.chapters.service import ChapterService
from app.modules.downloads.keys import chapter_object_key, combined_object_key
from app.modules.downloads.models import DownloadJob
from app.modules.downloads.repository import DownloadRepository


async def run_download_job(_ctx: object, job_id: str) -> None:
    """Synthesize chapter range, upload per-chapter + merged MP3."""
    from app.core.orm import import_all_models

    import_all_models()
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            await _process(session, UUID(job_id))
            await session.commit()
    finally:
        await engine.dispose()


async def _process(session: AsyncSession, job_id: UUID) -> None:
    repo = DownloadRepository(session)
    job = await repo.get_by_id(job_id)
    if job is None:
        return
    try:
        job.status = "running"
        await repo.flush()
        await session.commit()
        parts = await _synth_chapters(session, job)
        combined = await concat_mp3(parts)
        key = combined_object_key(job.user_id, job.id)
        await put_bytes(key, combined, "audio/mpeg")
        job.object_key = key
        job.status = "complete"
        job.error = None
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)[:2000]
    await repo.flush()


async def _synth_chapters(session: AsyncSession, job: DownloadJob) -> list[bytes]:
    chapters = ChapterService(session)
    summaries = await chapters.list_summaries(job.book_id)
    selected = [
        item for item in summaries if job.chapter_from <= item.chapter_number <= job.chapter_to
    ]
    selected.sort(key=lambda item: item.chapter_number)
    provider = get_provider(job.provider)
    rate = float(job.rate)
    parts: list[bytes] = []
    repo = DownloadRepository(session)
    for summary in selected:
        full = await chapters.get(summary.id)
        audio = await provider.synthesize(full.content, job.voice, rate)
        parts.append(audio)
        key = chapter_object_key(job.user_id, job.id, summary.chapter_number)
        await put_bytes(key, audio, "audio/mpeg")
        job.ready_count = len(parts)
        await repo.flush()
        await session.commit()
    return parts
