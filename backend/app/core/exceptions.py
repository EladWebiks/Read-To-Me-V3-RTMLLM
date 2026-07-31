"""Map domain exceptions to HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.audio.exceptions import (
    SynthesisError,
    TextTooLongError,
    UnknownProviderError,
)
from app.modules.auth.exceptions import (
    GoogleNotConfiguredError,
    NotAuthenticatedError,
    NotAuthorizedError,
)
from app.modules.books.exceptions import BookNotFoundError
from app.modules.chapters.exceptions import (
    ChapterNotFoundError,
    ChapterNumberConflictError,
)
from app.modules.discovery.exceptions import (
    DiscoveredBookNotFoundError,
    DiscoverySearchError,
)
from app.modules.downloads.exceptions import (
    DownloadJobNotFoundError,
    DownloadNotReadyError,
    InvalidChapterRangeError,
)
from app.modules.imports.exceptions import ImportJobNotFoundError, InvalidEpubUploadError
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.llm.exceptions import (
    AdapterNotRegisteredError,
    CapabilityNotSupportedError,
    CatalogModelNotFoundError,
    CatalogProviderNotFoundError,
    ConversationNotFoundError,
    DuplicateCatalogModelError,
    LlmConfigError,
    LlmDisabledError,
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
    NoCandidateModelError,
)
from app.modules.quotas.exceptions import QuotaExceededError, QuotaRuleNotFoundError
from app.modules.reader.exceptions import ProgressNotFoundError
from app.modules.runtime_config.exceptions import (
    OverrideNotFoundError,
    SettingValueInvalidError,
    UnknownSettingKeyError,
)
from app.modules.scraping.exceptions import (
    PreviewError,
    ScrapeJobAlreadyCancelledError,
    ScrapeJobNotDeletableError,
    ScrapeJobNotFoundError,
    UnsupportedSourceError,
)
from app.modules.users.exceptions import (
    AdminSelfActionError,
    LastAdminError,
    UserAccountDisabledError,
    UserAlreadyExistsError,
    UserNotFoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach domain-exception → HTTP status mappings."""
    _register_auth_handlers(app)
    _register_admin_user_handlers(app)
    _register_library_handlers(app)
    _register_audio_handlers(app)
    _register_download_handlers(app)
    _register_scraping_handlers(app)
    _register_import_handlers(app)
    _register_discovery_handlers(app)
    _register_llm_handlers(app)
    _register_llm_catalog_handlers(app)
    _register_runtime_config_handlers(app)
    _register_quota_handlers(app)


def _register_quota_handlers(app: FastAPI) -> None:
    @app.exception_handler(QuotaExceededError)
    async def _quota_exceeded(
        _request: Request,
        exc: QuotaExceededError,
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(QuotaRuleNotFoundError)
    async def _quota_rule_missing(
        _request: Request,
        _exc: QuotaRuleNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Quota rule not found"})


def _register_auth_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotAuthenticatedError)
    async def _not_authenticated(
        _request: Request,
        _exc: NotAuthenticatedError,
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    @app.exception_handler(NotAuthorizedError)
    async def _not_authorized(
        _request: Request,
        _exc: NotAuthorizedError,
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Not authorized"})

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

    @app.exception_handler(UserAccountDisabledError)
    async def _user_disabled(
        _request: Request,
        _exc: UserAccountDisabledError,
    ) -> JSONResponse:
        # 403, not 401: the caller's identity is established (a verified Google
        # identity, or a valid session) — it is the account that is not allowed
        # to be used, which is the same shape as NotAuthorizedError above. A 401
        # would invite the client to retry with credentials, and no credential
        # can help until an admin restores the account.
        return JSONResponse(status_code=403, content={"detail": "This account is disabled"})

    @app.exception_handler(GoogleNotConfiguredError)
    async def _google_not_configured(
        _request: Request,
        _exc: GoogleNotConfiguredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Google sign-in is not configured"},
        )


def _register_admin_user_handlers(app: FastAPI) -> None:
    @app.exception_handler(AdminSelfActionError)
    async def _admin_self_action(
        _request: Request,
        _exc: AdminSelfActionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Admins cannot demote or delete their own account"},
        )

    @app.exception_handler(LastAdminError)
    async def _last_admin(
        _request: Request,
        _exc: LastAdminError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "At least one active admin must remain"},
        )


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

    @app.exception_handler(ScrapeJobNotDeletableError)
    async def _scrape_not_deletable(
        _request: Request,
        _exc: ScrapeJobNotDeletableError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Cancel the job before removing it from history"},
        )

    @app.exception_handler(PreviewError)
    async def _preview_failed(
        _request: Request,
        _exc: PreviewError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(_exc)})


def _register_import_handlers(app: FastAPI) -> None:
    @app.exception_handler(ImportJobNotFoundError)
    async def _import_job_missing(
        _request: Request,
        _exc: ImportJobNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Import job not found"})

    @app.exception_handler(InvalidEpubUploadError)
    async def _invalid_epub(
        _request: Request,
        _exc: InvalidEpubUploadError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(_exc)})


def _register_discovery_handlers(app: FastAPI) -> None:
    @app.exception_handler(DiscoverySearchError)
    async def _discovery_search_failed(
        _request: Request,
        _exc: DiscoverySearchError,
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(_exc)})

    @app.exception_handler(DiscoveredBookNotFoundError)
    async def _discovered_missing(
        _request: Request,
        _exc: DiscoveredBookNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Discovered book not found"})


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


def _register_llm_handlers(app: FastAPI) -> None:
    @app.exception_handler(LlmDisabledError)
    async def _llm_disabled(
        _request: Request,
        _exc: LlmDisabledError,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "LLM is disabled"})

    @app.exception_handler(LlmConfigError)
    async def _llm_config(
        _request: Request,
        exc: LlmConfigError,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(CapabilityNotSupportedError)
    async def _llm_capability(
        _request: Request,
        exc: CapabilityNotSupportedError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(LlmRateLimitError)
    async def _llm_rate(
        _request: Request,
        exc: LlmRateLimitError,
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(LlmTimeoutError)
    async def _llm_timeout(
        _request: Request,
        exc: LlmTimeoutError,
    ) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": str(exc)})

    @app.exception_handler(NoCandidateModelError)
    async def _llm_no_candidate(
        _request: Request,
        exc: NoCandidateModelError,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ConversationNotFoundError)
    async def _llm_conversation_missing(
        _request: Request,
        exc: ConversationNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(LlmProviderError)
    async def _llm_provider(
        _request: Request,
        exc: LlmProviderError,
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})


def _register_runtime_config_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnknownSettingKeyError)
    async def _unknown_setting(
        _request: Request,
        exc: UnknownSettingKeyError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(OverrideNotFoundError)
    async def _override_missing(
        _request: Request,
        exc: OverrideNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(SettingValueInvalidError)
    async def _setting_invalid(
        _request: Request,
        exc: SettingValueInvalidError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})


def _register_llm_catalog_handlers(app: FastAPI) -> None:
    @app.exception_handler(CatalogProviderNotFoundError)
    async def _catalog_provider_missing(
        _request: Request,
        exc: CatalogProviderNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Unknown provider: {exc}"})

    @app.exception_handler(CatalogModelNotFoundError)
    async def _catalog_model_missing(
        _request: Request,
        exc: CatalogModelNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Unknown model: {exc}"})

    @app.exception_handler(AdapterNotRegisteredError)
    async def _catalog_no_adapter(
        _request: Request,
        exc: AdapterNotRegisteredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": f"No adapter registered for provider: {exc}"},
        )

    @app.exception_handler(DuplicateCatalogModelError)
    async def _catalog_duplicate(
        _request: Request,
        exc: DuplicateCatalogModelError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": f"Model already exists: {exc}"})
