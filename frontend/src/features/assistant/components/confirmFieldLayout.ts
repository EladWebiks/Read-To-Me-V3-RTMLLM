import type { ConfirmationFormField } from '../api/chatApi'

/** Field pairs rendered on one row in the HITL form. */
const FIELD_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['chapter_from', 'chapter_to'],
  ['start_chapter', 'chapter_count'],
  ['provider', 'rate'],
]

const SHORT_LABELS: Record<string, string> = {
  chapter_from: 'From',
  chapter_to: 'To (inclusive)',
  start_chapter: 'From',
  chapter_count: 'Count',
  provider: 'Provider',
  voice: 'Voice',
  rate: 'Rate',
}

/** Group fields into rows; preserve declaration order. */
export function fieldRows(fields: ConfirmationFormField[]): ConfirmationFormField[][] {
  const byName = new Map(fields.map((field) => [field.name, field]))
  const used = new Set<string>()
  const rows: ConfirmationFormField[][] = []
  for (const field of fields) {
    if (used.has(field.name)) continue
    const pair = FIELD_PAIRS.find(([a, b]) => a === field.name || b === field.name)
    const left = pair ? byName.get(pair[0]) : undefined
    const right = pair ? byName.get(pair[1]) : undefined
    if (left && right) {
      rows.push([left, right])
      used.add(left.name)
      used.add(right.name)
      continue
    }
    rows.push([field])
    used.add(field.name)
  }
  return rows
}

export function shortLabel(field: ConfirmationFormField): string {
  return SHORT_LABELS[field.name] ?? field.label
}

/** Subtitle duplicates editable chapter range — skip it on the card. */
export function showConfirmSubtitle(
  subtitle: string | null | undefined,
  fields: ConfirmationFormField[],
): boolean {
  if (!subtitle?.trim()) return false
  return !fields.some(
    (field) => field.name === 'chapter_from' || field.name === 'start_chapter',
  )
}
