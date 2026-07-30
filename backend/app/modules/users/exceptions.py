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


class UserAccountDisabledError(UserError):
    """A soft-deleted account tried to sign in again.

    Soft-deleted identities stay *reserved*: the row keeps its username, email
    and google_sub (the unique constraints are full, not partial), so sign-in
    must be refused rather than silently re-provisioning a parallel account or
    dying on a unique index. Only an explicit admin restore re-opens it.
    """


class AdminSelfActionError(UserError):
    """An admin tried to demote or soft-delete their own account."""


class LastAdminError(UserError):
    """The operation would leave zero active (non-deleted) admins."""
