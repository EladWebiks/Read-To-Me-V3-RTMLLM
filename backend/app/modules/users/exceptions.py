"""User domain exceptions."""


class UserError(Exception):
    """Base class for user-domain errors."""


class UserNotFoundError(UserError):
    """Raised when a user cannot be found."""


class UserAlreadyExistsError(UserError):
    """Raised when creating a user with a taken username."""
