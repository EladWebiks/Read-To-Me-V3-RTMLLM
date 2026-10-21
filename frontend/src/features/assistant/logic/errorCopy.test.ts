import { describe, expect, it } from 'vitest'
import '@/shared/i18n'
import { chatErrorMessage } from './errorCopy'

describe('chatErrorMessage', () => {
  it('keeps short plain errors', () => {
    expect(chatErrorMessage('Conversation not found')).toBe('Conversation not found')
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

  it('maps Gemini high-demand dumps to a short busy message', () => {
    const dump =
      '503 Service Unavailable. {\'message\': \'{\\n  "error": {\\n    "code": 503,\\n    "message": "This model is currently experiencing high demand.",\\n    "status": "UNAVAILABLE"\\n  }\\n}\\n\', \'status\': \'Service Unavailable\'}'
    expect(chatErrorMessage(dump)).toBe(
      'The AI service is busy right now. Please try again in a moment.',
    )
  })

  it('maps rate-limit and timeout wording', () => {
    expect(chatErrorMessage('429 rate limit exceeded')).toContain('Too many AI requests')
    expect(chatErrorMessage('Request timeout')).toContain('took too long')
  })
})
