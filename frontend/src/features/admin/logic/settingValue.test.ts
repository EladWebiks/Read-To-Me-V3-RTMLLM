import { describe, expect, it } from 'vitest'
import { formatValue, parseValue } from './settingValue'

describe('settingValue', () => {
  it('round-trips JSON scalars', () => {
    expect(parseValue('3')).toBe(3)
    expect(parseValue('true')).toBe(true)
    expect(parseValue('"internal_only"')).toBe('internal_only')
    expect(formatValue(3)).toBe('3')
    expect(formatValue('internal_only')).toBe('"internal_only"')
  })

  it('treats unquoted text as a plain string', () => {
    expect(parseValue('internal_only')).toBe('internal_only')
  })
})
