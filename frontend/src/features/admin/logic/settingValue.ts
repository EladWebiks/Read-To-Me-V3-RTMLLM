/** Values are whitelisted JSON scalars/lists; edit them as JSON text. */
export function formatValue(value: unknown): string {
  return value === undefined ? '' : JSON.stringify(value)
}

/** JSON when it parses; otherwise treat the raw text as a plain string. */
export function parseValue(text: string): unknown {
  const trimmed = text.trim()
  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    return trimmed
  }
}
