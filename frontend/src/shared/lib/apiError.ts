/** Readable text for a pydantic 422 body, whose `detail` is a LIST, not a string.
 *
 * Without this every validation failure reads "Request failed: 422", which tells
 * an admin nothing about which field the API refused or why.
 */

type ValidationItem = { loc?: unknown; msg?: unknown }

/** Request-part prefixes FastAPI puts in `loc`; they mean nothing to a reader. */
const LOCATIONS = new Set(['body', 'path', 'query', 'header', 'cookie'])

function fieldOf(loc: unknown): string {
  if (!Array.isArray(loc)) return ''
  return loc
    .filter((part): part is string => typeof part === 'string' && !LOCATIONS.has(part))
    .join('.')
}

/** e.g. 'limit_value: Input should be greater than or equal to 0'; null if unrecognised. */
export function validationDetail(detail: unknown): string | null {
  if (!Array.isArray(detail)) return null
  const lines = (detail as ValidationItem[]).flatMap((entry) => {
    const message = entry?.msg
    if (typeof message !== 'string') return []
    const field = fieldOf(entry?.loc)
    return [field ? `${field}: ${message}` : message]
  })
  return lines.length > 0 ? lines.join('; ') : null
}
