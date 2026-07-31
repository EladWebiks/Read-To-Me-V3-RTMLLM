"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.bootstrap import seed_admin_user
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.orm import import_all_models
from app.modules.admin.router import router as admin_router
from app.modules.audio.router import router as audio_router
from app.modules.auth.router import router as auth_router
from app.modules.chapters.router import router as chapters_router
from app.modules.discovery.router import router as discovery_router
from app.modules.downloads.router import router as downloads_router
from app.modules.health.router import router as health_router
from app.modules.imports.router import router as imports_router
from app.modules.library.router import router as library_router
from app.modules.llm.admin_router import router as llm_admin_router
from app.modules.llm.router import chat_router
from app.modules.llm.router import router as llm_router
from app.modules.llm.seed import seed_llm_models
from app.modules.orchestration.admin_router import (
    router as membership_admin_router,
)
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.quotas.admin_router import router as quotas_admin_router
from app.modules.quotas.admin_router import user_router as user_quotas_router
from app.modules.reader.router import router as reader_router
from app.modules.runtime_config.router import router as runtime_config_router
from app.modules.scraping.router import router as scraping_router
from app.modules.scraping.seed import seed_scraping_sources
from app.modules.usage.router import router as usage_router
from app.modules.users.me_router import router as me_plans_router
from app.modules.users.seed import seed_default_membership


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hook (startup/shutdown)."""
    import_all_models()
    # Tiers first: user creation FKs to memberships.slug and the policy seed
    # reads the registry to know which tiers exist.
    await seed_default_membership()
    await seed_admin_user()
    await seed_scraping_sources()
    await seed_llm_models()
    await seed_membership_policies()
    yield


def _register_routers(app: FastAPI, api_prefix: str) -> None:
    app.include_router(health_router, prefix=api_prefix)
    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(library_router, prefix=api_prefix)
    app.include_router(chapters_router, prefix=api_prefix)
    app.include_router(reader_router, prefix=api_prefix)
    app.include_router(audio_router, prefix=api_prefix)
    app.include_router(downloads_router, prefix=api_prefix)
    app.include_router(scraping_router, prefix=api_prefix)
    app.include_router(imports_router, prefix=api_prefix)
    app.include_router(discovery_router, prefix=api_prefix)
    app.include_router(usage_router, prefix=api_prefix)
    app.include_router(me_plans_router, prefix=api_prefix)
    app.include_router(llm_router, prefix=api_prefix)
    app.include_router(chat_router, prefix=api_prefix)
    app.include_router(llm_admin_router, prefix=api_prefix)
    app.include_router(membership_admin_router, prefix=api_prefix)
    app.include_router(quotas_admin_router, prefix=api_prefix)
    app.include_router(user_quotas_router, prefix=api_prefix)
    app.include_router(runtime_config_router, prefix=api_prefix)
    app.include_router(admin_router, prefix=api_prefix)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(debug=settings.app.debug)

    app = FastAPI(
        title=settings.app.name,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    _register_routers(app, settings.app.api_prefix)
    return app


app = create_app()
