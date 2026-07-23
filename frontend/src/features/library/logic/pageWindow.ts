/** Build a compact page number window with ellipses for large page counts. */
export function pageWindow(page: number, pageCount: number): (number | '…')[] {
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, i) => i + 1)
  }
  const set = new Set(
    [1, pageCount, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pageCount),
  )
  const sorted = [...set].sort((a, b) => a - b)
  const out: (number | '…')[] = []
  for (let i = 0; i < sorted.length; i += 1) {
    const n = sorted[i]!
    if (i > 0 && n - sorted[i - 1]! > 1) out.push('…')
    out.push(n)
  }
  return out
}
