import { describe, expect, it } from 'vitest'
import { QUOTA_INPUT_ERROR, parseQuotaInput } from './quotaFields'

describe('parseQuotaInput', () => {
  it('reads blank as clearing the rule (unlimited)', () => {
    expect(parseQuotaInput('')).toEqual({ ok: true, value: null })
    expect(parseQuotaInput('   ')).toEqual({ ok: true, value: null })
  })

  it('reads 0 as a real limit, not as blank', () => {
    expect(parseQuotaInput('0')).toEqual({ ok: true, value: 0 })
  })

  it('reads ordinary numbers', () => {
    expect(parseQuotaInput('500000')).toEqual({ ok: true, value: 500000 })
    expect(parseQuotaInput(' 12.5 ')).toEqual({ ok: true, value: 12.5 })
  })

  it('rejects negatives, which the API would 422 on', () => {
    expect(parseQuotaInput('-1')).toEqual({ ok: false, error: QUOTA_INPUT_ERROR })
  })

  it('rejects text and other non-numbers instead of failing silently', () => {
    expect(parseQuotaInput('abc')).toEqual({ ok: false, error: QUOTA_INPUT_ERROR })
    expect(parseQuotaInput('1,000')).toEqual({ ok: false, error: QUOTA_INPUT_ERROR })
    expect(parseQuotaInput('Infinity')).toEqual({ ok: false, error: QUOTA_INPUT_ERROR })
    expect(parseQuotaInput('NaN')).toEqual({ ok: false, error: QUOTA_INPUT_ERROR })
  })
})
