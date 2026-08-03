import { describe, expect, it } from 'vitest'
import type { ConfirmationFormField } from '../api/chatApi'
import { fieldRows, shortLabel, showConfirmSubtitle } from './confirmFieldLayout'

function field(name: string, label = name): ConfirmationFormField {
  return { name, label, type: 'integer', required: true, default: 1 }
}

describe('confirmFieldLayout', () => {
  it('pairs chapter range and provider/rate on shared rows', () => {
    const rows = fieldRows([
      field('chapter_from', 'First chapter'),
      field('chapter_to', 'Last chapter'),
      field('provider', 'TTS provider'),
      field('voice', 'TTS voice'),
      field('rate', 'Speech rate'),
    ])
    expect(rows.map((row) => row.map((item) => item.name))).toEqual([
      ['chapter_from', 'chapter_to'],
      ['provider', 'rate'],
      ['voice'],
    ])
  })

  it('shortens range and TTS labels', () => {
    expect(shortLabel(field('chapter_to', 'Last chapter number, inclusive'))).toBe(
      'To (inclusive)',
    )
    expect(shortLabel(field('provider', 'TTS provider'))).toBe('Provider')
    expect(shortLabel(field('voice', 'TTS voice (blank uses provider default)'))).toBe(
      'Voice',
    )
  })

  it('hides subtitle when chapter fields are editable', () => {
    expect(
      showConfirmSubtitle('Chapters 5-8', [field('chapter_from'), field('chapter_to')]),
    ).toBe(false)
    expect(showConfirmSubtitle('novelbin', [field('start_chapter')])).toBe(false)
    expect(showConfirmSubtitle('novelbin', [])).toBe(true)
  })
})
