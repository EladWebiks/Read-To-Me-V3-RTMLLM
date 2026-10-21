import type { ConfirmationFormField } from '../api/chatApi'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import i18n from '@/shared/i18n'

/** Field pairs rendered on one row in the HITL form. */
const FIELD_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['chapter_from', 'chapter_to'],
  ['start_chapter', 'chapter_count'],
  ['provider', 'rate'],
]

const SHORT_LABEL_KEYS = [
  'chapter_from',
  'chapter_to',
  'start_chapter',
  'chapter_count',
  'provider',
  'voice',
  'rate',
] as const

type ShortLabelKey = (typeof SHORT_LABEL_KEYS)[number]

function isShortLabelKey(name: string): name is ShortLabelKey {
  return (SHORT_LABEL_KEYS as readonly string[]).includes(name)
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

export function shortLabel(field: ConfirmationFormField, lng: ChatUiLang = 'en'): string {
  if (isShortLabelKey(field.name)) {
    return i18n.t(`assistant:fields.${field.name}`, { lng })
  }
  return field.label
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
