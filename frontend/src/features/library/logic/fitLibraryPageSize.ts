/** Matches LibraryGrid: auto-rows-40 (10rem) gap-y-4 pt-1; cols at sm/xl. */
export const LIBRARY_CARD_ROW_REM = 10
export const LIBRARY_ROW_GAP_REM = 1
export const LIBRARY_GRID_PAD_REM = 0.25

export function libraryColumnCount(viewportWidth: number): number {
  if (viewportWidth >= 1280) return 3
  if (viewportWidth >= 640) return 2
  return 1
}

/** How many cards fit in the grid slot without overflowing. */
export function fitLibraryPageSize(opts: {
  gridHeightPx: number
  viewportWidth: number
  remPx: number
}): number {
  const rowH = LIBRARY_CARD_ROW_REM * opts.remPx
  const gap = LIBRARY_ROW_GAP_REM * opts.remPx
  const pad = LIBRARY_GRID_PAD_REM * opts.remPx
  const cols = libraryColumnCount(opts.viewportWidth)
  const usable = Math.max(0, opts.gridHeightPx - pad - 2)
  const rows = Math.max(1, Math.floor((usable + gap) / (rowH + gap)))
  return rows * cols
}
