import { describe, expect, it } from 'vitest'
import { parsePolicyInput, placeholderFor, POLICY_FIELDS } from './policyFields'

describe('parsePolicyInput', () => {
  it('maps blank to null (inherit)', () => {
    expect(parsePolicyInput('')).toBeNull()
    expect(parsePolicyInput('   ')).toBeNull()
  })
  it('parses numbers', () => {
    expect(parsePolicyInput('42')).toBe(42)
    expect(parsePolicyInput('0.25')).toBe(0.25)
  })
  it('rejects garbage and negatives as undefined (invalid)', () => {
    expect(parsePolicyInput('abc')).toBeUndefined()
    expect(parsePolicyInput('-3')).toBeUndefined()
  })
})

describe('placeholderFor', () => {
  it('shows the inherited value for per-turn fields', () => {
    const meta = POLICY_FIELDS.find((f) => f.key === 'max_tool_iters')!
    expect(placeholderFor(meta, { max_tool_iters: 6 })).toBe('inherit (6)')
  })
  it('falls back gracefully when the inherited value is missing', () => {
    const meta = POLICY_FIELDS.find((f) => f.key === 'max_hitl_rounds')!
    expect(placeholderFor(meta, {})).toBe('inherit (—)')
  })
})
