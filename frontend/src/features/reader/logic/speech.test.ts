import { describe, expect, it } from 'vitest'
import { charIndexToWordIndex, paragraphText } from './speech'

describe('charIndexToWordIndex', () => {
  it('maps the start of each word', () => {
    const words = ['Hello', 'world', 'again']
    expect(charIndexToWordIndex(words, 0)).toBe(0)
    expect(charIndexToWordIndex(words, 6)).toBe(1)
    expect(charIndexToWordIndex(words, 12)).toBe(2)
  })

  it('clamps past the end to the last word', () => {
    expect(charIndexToWordIndex(['a', 'b'], 99)).toBe(1)
  })

  it('returns 0 for empty paragraphs', () => {
    expect(charIndexToWordIndex([], 5)).toBe(0)
  })
})

describe('paragraphText', () => {
  it('joins words with spaces', () => {
    expect(paragraphText(['Once', 'upon', 'a', 'time'])).toBe('Once upon a time')
  })
})
