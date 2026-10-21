/** How many table body rows fit in a slot after reserving the thead. */
export function fitTablePageSize(opts: {
  slotHeightPx: number
  headerHeightPx: number
  rowHeightPx: number
}): number {
  if (opts.slotHeightPx < 32 || opts.rowHeightPx < 8) return 0
  const usable = Math.max(0, opts.slotHeightPx - opts.headerHeightPx - 2)
  return Math.max(1, Math.floor(usable / opts.rowHeightPx))
}
