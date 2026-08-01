import { describe, expect, it } from 'vitest'
import { formatAmount, meterPercent, meterState, resetLabel } from './format'

describe('meterState', () => {
  it('is unlimited when limit is null', () => {
    expect(meterState(999, null)).toBe('unlimited')
  })
  it('is over — never unlimited — when the limit is 0', () => {
    expect(meterState(0, 0)).toBe('over')
    expect(meterState(5, 0)).toBe('over')
  })
  it('is ok under 80%, warn from 80%, over from 100%', () => {
    expect(meterState(79, 100)).toBe('ok')
    expect(meterState(80, 100)).toBe('warn')
    expect(meterState(99, 100)).toBe('warn')
    expect(meterState(100, 100)).toBe('over')
    expect(meterState(150, 100)).toBe('over')
  })
})

describe('meterPercent', () => {
  it('clamps to 0..100 and handles null limit', () => {
    expect(meterPercent(50, 100)).toBe(50)
    expect(meterPercent(150, 100)).toBe(100)
    expect(meterPercent(10, null)).toBe(0)
  })
  it('is full at a 0 limit rather than empty', () => {
    expect(meterPercent(0, 0)).toBe(100)
  })
})

describe('formatAmount', () => {
  it('formats bytes as MB/GB', () => {
    expect(formatAmount(52428800, 'bytes')).toBe('50.0 MB')
    expect(formatAmount(2147483648, 'bytes')).toBe('2.0 GB')
  })
  it('formats USD with two decimals and tokens with separators', () => {
    expect(formatAmount(1.5, 'USD')).toBe('$1.50')
    expect(formatAmount(1234567, 'tokens')).toBe('1,234,567')
  })
})

describe('resetLabel', () => {
  it('renders a readable date and falls back gracefully', () => {
    expect(resetLabel('2026-08-01T00:00:00+00:00')).toContain('2026')
    expect(resetLabel('not-a-date')).toBe('next month')
  })
})
