import { describe, expect, it } from 'vitest'
import { chatErrorMessage } from './errorCopy'

describe('chatErrorMessage', () => {
  it('passes ordinary errors through', () => {
    expect(chatErrorMessage('something broke')).toBe('something broke')
    expect(chatErrorMessage('boom', 'budget_exceeded')).toBe('boom')
  })

  it('maps quota_exceeded to friendly copy with the rollover date', () => {
    const message = chatErrorMessage(
      'Monthly AI tokens quota reached (110/100 tokens). Resets 2026-08-01.',
      'quota_exceeded',
      '2026-08-01T00:00:00+00:00',
    )
    expect(message).toContain('monthly AI limit')
    expect(message).toContain('2026')
  })

  it('falls back to "next month" for a missing/invalid date', () => {
    expect(chatErrorMessage('x', 'quota_exceeded')).toContain('next month')
    expect(chatErrorMessage('x', 'quota_exceeded', 'not-a-date')).toContain('next month')
  })
})
