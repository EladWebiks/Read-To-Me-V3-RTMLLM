import { describe, expect, it } from 'vitest'
import { fitLibraryPageSize, libraryColumnCount } from './fitLibraryPageSize'

describe('libraryColumnCount', () => {
  it('matches Tailwind sm / xl breakpoints', () => {
    expect(libraryColumnCount(375)).toBe(1)
    expect(libraryColumnCount(640)).toBe(2)
    expect(libraryColumnCount(1279)).toBe(2)
    expect(libraryColumnCount(1280)).toBe(3)
  })
})

describe('fitLibraryPageSize', () => {
  it('packs full rows into the measured height', () => {
    // 3 rows at 16px rem: usable >= 3*160 + 2*16 → height >= 4+2+512 = 518
    expect(
      fitLibraryPageSize({ gridHeightPx: 518, viewportWidth: 1280, remPx: 16 }),
    ).toBe(9)
  })

  it('never returns less than one row of columns', () => {
    expect(fitLibraryPageSize({ gridHeightPx: 40, viewportWidth: 1280, remPx: 16 })).toBe(
      3,
    )
  })
})
