import { describe, expect, it } from 'vitest'
import { truncateHistoryTitle } from './truncateHistoryTitle'

describe('truncateHistoryTitle', () => {
  it('uses a fallback for empty titles', () => {
    expect(truncateHistoryTitle(null)).toBe('Untitled chat')
    expect(truncateHistoryTitle('   ')).toBe('Untitled chat')
  })

  it('keeps short titles intact', () => {
    expect(truncateHistoryTitle('Find Against the Gods')).toBe('Find Against the Gods')
  })

  it('truncates long titles with an ellipsis', () => {
    const long = 'a'.repeat(90)
    const out = truncateHistoryTitle(long)
    expect(out.endsWith('…')).toBe(true)
    expect(out.length).toBe(72)
  })
})
