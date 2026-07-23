"""Map domain exceptions to HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.audio.exceptions import (
    SynthesisError,
    TextTooLongError,
    UnknownProviderError,
)
from app.modules.auth.exceptions import InvalidCredentialsError, NotAuthenticatedError
from app.modules.books.exceptions import BookNotFoundError
from app.modules.chapters.exceptions import (
    ChapterNotFoundError,
    ChapterNumberConflictError,
)
from app.modules.downloads.exceptions import (
    DownloadJobNotFoundError,
    DownloadNotReadyError,
    InvalidChapterRangeError,
)
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.reader.exceptions import ProgressNotFoundError
from app.modules.scraping.exceptions import (
    PreviewError,
    ScrapeJobAlreadyCancelledError,
    ScrapeJobNotFoundError,
    UnsupportedSourceError,
)
from app.modules.users.exceptions import UserAlreadyExistsError, UserNotFoundError


def register_exception_handlers(app: FastAPI) -> None:
    """Attach domain-exception → HTTP status mappings."""
    _register_auth_handlers(app)
    _register_library_handlers(app)
    _register_audio_handlers(app)
    _register_download_handlers(app)
    _register_scraping_handlers(app)


def _register_auth_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidCredentialsError)
    async def _invalid_credentials(
        _request: Request,
        _exc: InvalidCredentialsError,
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    @app.exception_handler(NotAuthenticatedError)
    async def _not_authenticated(
        _request: Request,
        _exc: NotAuthenticatedError,
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    @app.exception_handler(UserNotFoundError)
    async def _user_not_found(
        _request: Request,
        _exc: UserNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "User not found"})

    @app.exception_handler(UserAlreadyExistsError)
    async def _user_exists(
        _request: Request,
        _exc: UserAlreadyExistsError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "User already exists"})


def _register_library_handlers(app: FastAPI) -> None:
    @app.exception_handler(BookAccessDeniedError)
    async def _book_denied(
        _request: Request,
        _exc: BookAccessDeniedError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Book not found"})

    @app.exception_handler(BookNotFoundError)
    async def _book_missing(
        _request: Request,
        _exc: BookNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Book not found"})

    @app.exception_handler(ChapterNotFoundError)
    async def _chapter_missing(
        _request: Request,
        _exc: ChapterNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Chapter not found"})

    @app.exception_handler(ChapterNumberConflictError)
    async def _chapter_conflict(
        _request: Request,
        _exc: ChapterNumberConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Chapter number already exists"},
        )

    @app.exception_handler(ProgressNotFoundError)
    async def _progress_missing(
        _request: Request,
        _exc: ProgressNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "No reading progress"})


def _register_audio_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnknownProviderError)
    async def _unknown_provider(
        _request: Request,
        _exc: UnknownProviderError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Unknown TTS provider"})

    @app.exception_handler(TextTooLongError)
    async def _text_too_long(
        _request: Request,
        _exc: TextTooLongError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Text too long"})

    @app.exception_handler(SynthesisError)
    async def _synth_failed(
        _request: Request,
        _exc: SynthesisError,
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": "TTS synthesis failed"})


def _register_scraping_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnsupportedSourceError)
    async def _unsupported_source(
        _request: Request,
        _exc: UnsupportedSourceError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(_exc)})

    @app.exception_handler(ScrapeJobNotFoundError)
    async def _scrape_job_missing(
        _request: Request,
        _exc: ScrapeJobNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Scrape job not found"})

    @app.exception_handler(ScrapeJobAlreadyCancelledError)
    async def _scrape_already_cancelled(
        _request: Request,
        _exc: ScrapeJobAlreadyCancelledError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Job already terminal"})

    @app.exception_handler(PreviewError)
    async def _preview_failed(
        _request: Request,
        _exc: PreviewError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(_exc)})


def _register_download_handlers(app: FastAPI) -> None:
    @app.exception_handler(DownloadJobNotFoundError)
    async def _job_missing(
        _request: Request,
        _exc: DownloadJobNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Download job not found"})

    @app.exception_handler(DownloadNotReadyError)
    async def _job_not_ready(
        _request: Request,
        _exc: DownloadNotReadyError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Download not ready"})

    @app.exception_handler(InvalidChapterRangeError)
    async def _bad_range(
        _request: Request,
        _exc: InvalidChapterRangeError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Invalid chapter range"})
