"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.bootstrap import seed_admin_user
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.orm import import_all_models
from app.modules.audio.router import router as audio_router
from app.modules.auth.router import router as auth_router
from app.modules.chapters.router import router as chapters_router
from app.modules.downloads.router import router as downloads_router
from app.modules.health.router import router as health_router
from app.modules.library.router import router as library_router
from app.modules.llm.router import chat_router
from app.modules.llm.router import router as llm_router
from app.modules.llm.seed import seed_llm_models
from app.modules.reader.router import router as reader_router
from app.modules.scraping.router import router as scraping_router
from app.modules.scraping.seed import seed_scraping_sources


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hook (startup/shutdown)."""
    import_all_models()
    await seed_admin_user()
    await seed_scraping_sources()
    await seed_llm_models()
    yield


def _validate_llm_startup(settings: Settings) -> None:
    """Fail fast when LLM is on but the provider key is missing."""
    from app.modules.llm.exceptions import LlmConfigError

    if not settings.llm_enabled:
        return
    if settings.llm_provider == "gemini" and not settings.gemini_api_key:
        raise LlmConfigError("GEMINI_API_KEY is required when LLM_ENABLED=true")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(debug=settings.debug)
    _validate_llm_startup(settings)

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(library_router, prefix=settings.api_prefix)
    app.include_router(chapters_router, prefix=settings.api_prefix)
    app.include_router(reader_router, prefix=settings.api_prefix)
    app.include_router(audio_router, prefix=settings.api_prefix)
    app.include_router(downloads_router, prefix=settings.api_prefix)
    app.include_router(scraping_router, prefix=settings.api_prefix)
    app.include_router(llm_router, prefix=settings.api_prefix)
    app.include_router(chat_router, prefix=settings.api_prefix)
    return app


app = create_app()
