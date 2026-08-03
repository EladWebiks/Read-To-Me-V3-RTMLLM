import type { ConfirmationFormField } from '../api/chatApi'

/** Chapter range pairs rendered on one row in the HITL form. */
const RANGE_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['chapter_from', 'chapter_to'],
  ['start_chapter', 'chapter_count'],
]

const SHORT_LABELS: Record<string, string> = {
  chapter_from: 'From',
  chapter_to: 'To',
  start_chapter: 'From',
  chapter_count: 'Count',
}

/** Group fields so chapter ranges share a row; preserve declaration order. */
export function fieldRows(fields: ConfirmationFormField[]): ConfirmationFormField[][] {
  const byName = new Map(fields.map((field) => [field.name, field]))
  const used = new Set<string>()
  const rows: ConfirmationFormField[][] = []
  for (const field of fields) {
    if (used.has(field.name)) continue
    const pair = RANGE_PAIRS.find(([a, b]) => a === field.name || b === field.name)
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
