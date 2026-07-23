import { describe, expect, it } from 'vitest'
import { parseParagraphs } from './parseChapter'

describe('parseParagraphs', () => {
  it('splits on blank lines and whitespace', () => {
    const result = parseParagraphs('Hello world.\n\nNext paragraph here.')
    expect(result).toEqual([
      ['Hello', 'world.'],
      ['Next', 'paragraph', 'here.'],
    ])
  })

  it('returns empty for blank content', () => {
    expect(parseParagraphs('   \n\n  ')).toEqual([])
  })
})
