"""Build the default tool registry for a session."""

from __future__ import annotations

from app.modules.tools.definitions.create_chapter_download import (
    CreateChapterDownloadTool,
)
from app.modules.tools.definitions.get_book_details import GetBookDetailsTool
from app.modules.tools.definitions.get_chapter_content import GetChapterContentTool
from app.modules.tools.definitions.get_download_status import GetDownloadStatusTool
from app.modules.tools.definitions.get_reading_progress import GetReadingProgressTool
from app.modules.tools.definitions.get_recently_read_chapters import (
    GetRecentlyReadChaptersTool,
)
from app.modules.tools.definitions.list_available_chapters import (
    ListAvailableChaptersTool,
)
from app.modules.tools.definitions.play_chapter import PlayChapterTool
from app.modules.tools.definitions.resume_book import ResumeBookTool
from app.modules.tools.definitions.scrape_book_range import ScrapeBookRangeTool
from app.modules.tools.definitions.search_library_content import SearchLibraryContentTool
from app.modules.tools.definitions.search_user_books import SearchUserBooksTool
from app.modules.tools.registry import ToolRegistry


def build_default_registry() -> ToolRegistry:
    """Registry with B3.1-B3.3 tools (scrape is mode-gated)."""
    return ToolRegistry(
        [
            SearchUserBooksTool(),
            GetBookDetailsTool(),
            SearchLibraryContentTool(),
            GetReadingProgressTool(),
            GetRecentlyReadChaptersTool(),
            ListAvailableChaptersTool(),
            GetChapterContentTool(),
            GetDownloadStatusTool(),
            PlayChapterTool(),
            ResumeBookTool(),
            CreateChapterDownloadTool(),
            ScrapeBookRangeTool(),
        ]
    )
