"""Ensure all SQLAlchemy models are registered (FK resolution)."""

from __future__ import annotations


def import_all_models() -> None:
    """Import every mapped model so FK targets resolve during flush."""
    # Import order does not matter; side effect is mapper registration.
    from app.modules.books import models as books_models
    from app.modules.chapters import models as chapters_models
    from app.modules.discovery import models as discovery_models
    from app.modules.downloads import models as downloads_models
    from app.modules.library import models as library_models
    from app.modules.llm import models as llm_models
    from app.modules.reader import models as reader_models
    from app.modules.runtime_config import models as runtime_config_models
    from app.modules.scraping import models as scraping_models
    from app.modules.summaries import models as summaries_models
    from app.modules.users import models as users_models

    _ = (
        books_models,
        chapters_models,
        discovery_models,
        downloads_models,
        library_models,
        llm_models,
        reader_models,
        runtime_config_models,
        scraping_models,
        summaries_models,
        users_models,
    )
