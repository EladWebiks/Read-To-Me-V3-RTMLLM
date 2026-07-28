"""Discovery domain exceptions."""


class DiscoveryError(Exception):
    """Base discovery error."""


class DiscoverySearchError(DiscoveryError):
    """External or internal search failed."""


class DiscoveredBookNotFoundError(DiscoveryError):
    """No discovered book for the given id."""
