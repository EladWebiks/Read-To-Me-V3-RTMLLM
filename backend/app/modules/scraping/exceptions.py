"""Scraping module domain exceptions."""


class UnsupportedSourceError(Exception):
    """URL does not match any enabled scraping source."""


class ScrapeJobNotFoundError(Exception):
    """Scraping job missing or not owned."""


class ScrapeJobAlreadyCancelledError(Exception):
    """Cancel requested on a job that is already terminal."""


class PreviewError(Exception):
    """Could not generate a preview for the given URL."""
