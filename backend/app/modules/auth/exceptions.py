"""Auth domain exceptions."""


class AuthError(Exception):
    """Base class for auth errors."""


class InvalidCredentialsError(AuthError):
    """Raised when username/password are wrong."""


class NotAuthenticatedError(AuthError):
    """Raised when a request lacks a valid session."""
