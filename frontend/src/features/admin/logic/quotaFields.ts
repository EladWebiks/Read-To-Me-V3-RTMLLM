/** Parsing for admin quota inputs.
 *
 * Distinct from `parsePolicyInput`, which is for per-turn caps where blank
 * means "inherit": here blank means "delete the rule" (unlimited) and 0 is a
 * real limit that blocks the kind. Invalid input returns a message to show
 * rather than `undefined`, so a bad entry can never fail silently.
 */

export const QUOTA_INPUT_ERROR = 'Enter a number ≥ 0, or leave blank for unlimited.'

export type QuotaParse =
  | { ok: true; value: number | null } // null = clear the rule
  | { ok: false; error: string }

export function parseQuotaInput(raw: string): QuotaParse {
  const trimmed = raw.trim()
  if (trimmed === '') return { ok: true, value: null }
  const value = Number(trimmed)
  if (!Number.isFinite(value) || value < 0) {
    return { ok: false, error: QUOTA_INPUT_ERROR }
  }
  return { ok: true, value }
}
