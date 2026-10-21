import { describe, expect, it } from 'vitest'
import { fitAdminTablePageSize } from './fitAdminTablePageSize'

describe('fitAdminTablePageSize', () => {
  it('re-exports shared fitTablePageSize', () => {
    expect(
      fitAdminTablePageSize({
        slotHeightPx: 440,
        headerHeightPx: 40,
        rowHeightPx: 44,
      }),
    ).toBe(9)
  })
})
