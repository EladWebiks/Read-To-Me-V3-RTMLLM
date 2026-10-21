import { describe, expect, it } from 'vitest'
import { fitTablePageSize } from './fitTablePageSize'

describe('fitTablePageSize', () => {
  it('returns how many rows fit under the thead', () => {
    expect(
      fitTablePageSize({
        slotHeightPx: 440,
        headerHeightPx: 40,
        rowHeightPx: 44,
      }),
    ).toBe(9)
  })

  it('returns 0 when the slot is not laid out yet', () => {
    expect(
      fitTablePageSize({
        slotHeightPx: 0,
        headerHeightPx: 40,
        rowHeightPx: 44,
      }),
    ).toBe(0)
  })

  it('never returns less than 1 once the slot has height', () => {
    expect(
      fitTablePageSize({
        slotHeightPx: 50,
        headerHeightPx: 40,
        rowHeightPx: 44,
      }),
    ).toBe(1)
  })
})
