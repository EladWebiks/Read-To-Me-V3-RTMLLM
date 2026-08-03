import { describe, expect, it } from 'vitest'
import type { ConfirmationFormField } from '../api/chatApi'
import { fieldRows, shortLabel } from './confirmFieldLayout'

function field(name: string, label = name): ConfirmationFormField {
  return { name, label, type: 'integer', required: true, default: 1 }
}

describe('confirmFieldLayout', () => {
  it('pairs chapter_from and chapter_to on one row', () => {
    const rows = fieldRows([
      field('chapter_from', 'First chapter'),
      field('chapter_to', 'Last chapter'),
      field('provider', 'TTS provider'),
    ])
    expect(rows).toEqual([
      [
        expect.objectContaining({ name: 'chapter_from' }),
        expect.objectContaining({ name: 'chapter_to' }),
      ],
      [expect.objectContaining({ name: 'provider' })],
    ])
  })

  it('shortens range labels', () => {
    expect(shortLabel(field('chapter_from', 'First chapter number, inclusive'))).toBe(
      'From',
    )
    expect(shortLabel(field('chapter_to', 'Last chapter number, inclusive'))).toBe(
      'To (inclusive)',
    )
  })
})
