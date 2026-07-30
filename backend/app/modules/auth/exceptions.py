"""Auth domain exceptions."""


class AuthError(Exception):
    """Base class for auth errors."""


class NotAuthenticatedError(AuthError):
    """Raised when a request lacks a valid session."""


class GoogleAuthError(AuthError):
    """Google OAuth flow failed; `reason` is a machine-readable code."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class GoogleNotConfiguredError(AuthError):
    """Google OAuth settings are missing."""
