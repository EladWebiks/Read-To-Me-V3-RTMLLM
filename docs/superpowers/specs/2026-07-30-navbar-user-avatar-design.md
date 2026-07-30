# Navbar user avatar — design

**Date:** 2026-07-30
**Status:** approved (autonomous session — defaults chosen and recorded here)

## Goal

Replace the plain username text ("admin") in the app-shell navbar with the
logged-in user's Google profile image; hovering the image shows the user's
email in a tooltip.

## Current state

- `ShellActions` (frontend/src/layout/ShellActions.tsx) renders
  `data?.user.username` as a text span between the settings and logout buttons.
- The backend never captures Google's `picture` claim: `GoogleClaims` only
  models `sub`, `email`, `email_verified`, `name`; the `users` table has no
  picture column; `/api/auth/me` returns `UserRead` without one.

## Decisions (with alternatives considered)

1. **Store the Google picture URL on the user row and hot-link it.**
   Alternative — proxy/download the image into MinIO — rejected as YAGNI: the
   URL is served by Google's CDN, and the blob rule ("all blobs in MinIO")
   targets app-owned content, not a third-party avatar hyperlink. The `<img>`
   uses `referrerPolicy="no-referrer"` (googleusercontent 403s some referred
   requests).
2. **Refresh the stored URL on every Google login** (pictures change/rotate).
   A `None` picture claim leaves the stored value untouched rather than wiping
   it — missing claims are treated as "no information", not "removed".
3. **Tooltip content = email, falling back to username** when email is null
   (e.g. a legacy seeded row). Uses the existing `IconTooltip` wrapper already
   used by the neighboring shell buttons.
4. **Fallback avatar** when there is no picture or the image fails to load: a
   circle with the username's first letter (uppercase), themed with
   muted background — no external dependency.
5. The avatar is displayed at all viewport sizes (the old text was hidden on
   mobile; a 28px image costs no meaningful space).

## Changes

### Backend

- `GoogleClaims`: add `picture: str | None = None`.
- `users.models.User`: add `picture_url: Mapped[str | None]`
  (`String(1024)`, nullable). Reversible Alembic migration (add/drop column).
- `users.schemas.UserRead`: add `picture_url: str | None` (flows into
  `/api/auth/me` automatically via `MeResponse`).
- `users.service`:
  - `link_google(..., picture_url: str | None = None)` and
    `create_from_google(..., picture_url: str | None = None)` stamp the column;
  - `resolve_google_identity(..., picture_url: str | None = None)` passes it
    through all four match paths and refreshes it for a returning `google_sub`
    match when the claim differs from the stored value.
- `auth.service.login_with_google`: pass `picture_url=claims.picture`.

### Frontend

- `features/auth/types.ts` `User`: add `picture_url: string | null`.
- New `layout/UserAvatar.tsx`: small component — image with initial-letter
  fallback (state flips on `onError`), wrapped in `IconTooltip` whose label is
  `email ?? username`.
- `layout/ShellActions.tsx`: replace the username span with `<UserAvatar />`.

## Error handling

- Broken/blocked image URL → `onError` swaps to the initial-letter fallback.
- No user loaded yet (`useMe` pending) → render nothing (same as today's
  `data?.user.username`).

## Testing

- Backend (extend existing integration tests): `create_from_google` and
  `link_google` persist `picture_url`; returning-sub login refreshes a changed
  picture; `None` claim leaves the stored picture untouched.
- Frontend (vitest): `UserAvatar` renders the image when `picture_url` is set
  and the letter fallback when it is null or the image errors.
