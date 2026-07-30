"""User domain exceptions."""


class UserError(Exception):
    """Base class for user-domain errors."""


class UserNotFoundError(UserError):
    """Raised when a user cannot be found."""


class UserAlreadyExistsError(UserError):
    """Raised when creating a user with a taken username."""


class GoogleIdentityConflictError(UserError):
    """Raised when an email match is already bound to a different Google subject.

    Lives in `users` (not `auth`) because the matching rules it guards live in
    `UserService`; `users` must never import from `auth`. `AuthService`
    translates it back into the wire-level `google_identity_conflict` reason.
    """
