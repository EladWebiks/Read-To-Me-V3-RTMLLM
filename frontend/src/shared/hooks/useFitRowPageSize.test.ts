import { describe, expect, it } from 'vitest'
import { fitRowPageSize } from './useFitRowPageSize'

describe('fitRowPageSize', () => {
  it('packs full rows into the measured height', () => {
    // 5 rows: usable >= 5*60 + 4*8 = 332 → slotHeight 334
    expect(
      fitRowPageSize({ slotHeightPx: 334, remPx: 16, rowRem: 3.75, gapRem: 0.5 }),
    ).toBe(5)
  })

  it('never returns less than one row', () => {
    expect(
      fitRowPageSize({ slotHeightPx: 10, remPx: 16, rowRem: 3.75, gapRem: 0.5 }),
    ).toBe(1)
  })
})
