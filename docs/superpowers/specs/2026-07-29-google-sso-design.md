# Google SSO (Google-only login, server-side code flow) — Design

Date: 2026-07-29
Status: Approved

## Goal

Replace username/password login with Google sign-in. The frontend shows a
"Sign in with Google" button that opens a small popup window; the backend owns
the entire OAuth 2.0 authorization-code flow and issues the app's existing
session cookie. No Google JavaScript runs in the app.

## Decisions (user-approved)

1. **Access policy:** anyone with a Google account auto-provisions a new RTM
   user on first sign-in (subject to the matching rules below).
2. **Password login is removed.** Google is the only way to sign in.
3. **Flow:** server-side authorization-code flow (backend-driven popup), not
   Google Identity Services JS.
4. **Admin-claim rule:** the first-ever Google sign-in (no user has a
   `google_sub` yet) claims the seeded `admin` account, preserving ownership of
   the existing library. Approved as designed.

## Data model & migration

One reversible Alembic migration on `users`:

- Add `google_sub: String(64) | NULL`, unique index — Google's stable subject
  ID; primary link key (emails can change, `sub` cannot).
- Make `password_hash` nullable — Google-provisioned users have no password.

## Account matching rules (evaluated in order at callback time)

1. User with matching `google_sub` → sign in.
2. User with matching **verified** email → link: stamp `google_sub` on it.
3. If **no user in the system has a `google_sub` yet** → claim the `admin`
   user: stamp `google_sub` and email onto it. (Single-user → multi-user
   bridge; can only ever fire once.)
4. Otherwise → auto-provision: username derived from the email local-part,
   deduped with a numeric suffix; role `user`; `password_hash` NULL.

## Backend

### Settings (`app/core/config.py`)

- `google_client_id: str | None`
- `google_client_secret: str | None`
- `google_redirect_uri: str | None` — browser-facing callback URL, e.g.
  `http://localhost:5173/api/auth/google/callback` (dev) or the `:3000`
  variant (docker). Both get registered in the Google Cloud console.

Per repo rules, added together to `.env.example`, `docker-compose.yml`
`environment` blocks (backend and worker kept in sync), and README. If unset,
the Google endpoints return a clear 503-style configuration error.

### OAuth client (`app/modules/auth/google.py`)

Small module, no new SDK:

- Builds the consent URL (`https://accounts.google.com/o/oauth2/v2/auth`,
  `scope=openid email profile`, `prompt=select_account`, `state`, PKCE not
  required for confidential clients but `state` is mandatory).
- Exchanges the code at `https://oauth2.googleapis.com/token` via async
  `httpx` with a strict timeout.
- Verifies the returned ID token with **PyJWT** (already a dependency) against
  Google's JWKS (fetched via httpx, cached in-process with expiry): checks
  signature, `aud == client_id`, `iss ∈ {accounts.google.com,
  https://accounts.google.com}`, `exp`, and requires `email_verified: true`.

### Routes (`app/modules/auth/router.py`)

- `GET /auth/google/login` — mints a random `state`, stores it in a
  short-lived (10 min) HttpOnly cookie, 302-redirects the popup to Google.
- `GET /auth/google/callback` — validates `state` (query vs cookie, then
  clears it), exchanges the code, verifies claims, runs the matching rules,
  sets the existing `rtm_token` HttpOnly cookie, and returns a minimal HTML
  page that does `window.opener.postMessage({type: 'rtm-google-auth', ok:
  true}, origin)` then `window.close()`. Error paths return the same page with
  `ok: false` and a machine-readable `reason` — the popup never strands the
  user.
- `POST /auth/login` (password) and its schemas are **removed**. `logout` and
  `me` are unchanged.

### Service (`app/modules/auth/service.py`)

- `AuthService.login_with_google(claims) -> tuple[UserRead, str]` implements
  the matching rules by calling `UserService` only (no repository access
  across modules). New `UserService` methods: `get_entity_by_email`,
  `get_entity_by_google_sub`, `any_google_linked`, `create_from_google`,
  `link_google`.
- `AuthService.login` (password) is removed. Admin seeding at startup stays —
  it anchors matching rule 3.

### Origin/proxy note

Dev (`:5173` Vite) and docker (`:3000` nginx) both proxy `/api` to the
backend, so the popup URL, callback page, and session cookie are all
same-origin with the frontend. `postMessage` uses that origin; no CORS
changes.

## Frontend

- `LoginPage` — password form deleted; renders a hand-styled
  "Sign in with Google" button per Google's branding spec (inline SVG "G",
  no external assets).
- New `useGoogleLogin` hook:
  - `window.open('/api/auth/google/login', 'rtm-google-auth',
    'width=500,height=600')`.
  - Origin-checked `message` listener; on `ok: true` → invalidate the `me`
    react-query cache and navigate to `/reader`.
  - Detects popup-blocked (`window.open` returns null) and
    closed-without-completing (poll `closed`) → inline error states.
- Password `useLogin`, its API call, and request types are removed; `logout`
  and `me` API calls unchanged.
- ESLint size caps respected: page, button component, and hook are separate
  files (≤110 lines each).

## Error handling & security

- `state` mismatch/missing → 400 via the error popup page.
- Google token-endpoint failure or timeout → error popup page; never a hung
  window.
- Unverified email → rejected.
- Authorization codes, tokens, and claims are never logged; the Google access
  token is discarded after the exchange (identity only). The client secret
  exists only in backend env.
- Authenticated identity continues to come only from the server-set cookie.

## Testing

- **Backend unit:** matching rules 1–4 (sub match, email link, admin claim,
  provision + username dedupe), ID-token claim validation (bad aud/iss/exp,
  unverified email).
- **Backend integration:** both endpoints with Google's token endpoint mocked
  (respx), state-mismatch rejection, cookie issuance, callback HTML shape.
- **Frontend vitest:** `useGoogleLogin` with mocked `window.open` and message
  events; LoginPage render + error states.
- Gates: `ruff check` + `format`, strict `mypy`, `pytest -m "unit or
  integration"`, `npm run lint`, `npm run build`, `npm run test`.

## Out of scope

- Refresh tokens / offline access (no Google APIs are called post-login).
- Account unlinking UI, multi-provider SSO, role management for provisioned
  users.

## Accepted risks (user-acknowledged)

- **Open provisioning:** any Google account that can reach the app gets a
  fresh account. Acceptable for a local-first app bound to localhost/LAN.
- **Google-only:** if Google is unreachable or misconfigured, nobody can sign
  in; local dev requires real Google OAuth credentials in `.env`.
