import { describe, expect, it } from 'vitest'
import i18n from '@/shared/i18n'
import { truncateHistoryTitle } from '../logic/truncateHistoryTitle'

describe('i18n assistant copy', () => {
  it('returns English strings from the assistant namespace', () => {
    expect(i18n.t('assistant:composer.placeholder')).toBe('Ask anything…')
    expect(i18n.t('assistant:hitl.approve')).toBe('Approve')
    expect(i18n.t('common:nav.library')).toBe('Library')
  })

  it('truncates long Hebrew history titles with the English untitled fallback', () => {
    expect(truncateHistoryTitle(null)).toBe('Untitled chat')
    const long = 'א'.repeat(80)
    const truncated = truncateHistoryTitle(long)
    expect(truncated.endsWith('…')).toBe(true)
    expect(truncated.length).toBe(72)
  })
})
