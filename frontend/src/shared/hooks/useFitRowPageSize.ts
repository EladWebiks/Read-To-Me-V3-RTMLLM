import { useEffect, useState, type RefObject } from 'react'

/** How many fixed-height rows fit in a measured slot (gap between rows). */
export function fitRowPageSize(opts: {
  slotHeightPx: number
  remPx: number
  rowRem: number
  gapRem: number
}): number {
  const rowH = opts.rowRem * opts.remPx
  const gap = opts.gapRem * opts.remPx
  const usable = Math.max(0, opts.slotHeightPx - 2)
  return Math.max(1, Math.floor((usable + gap) / (rowH + gap)))
}

/** Observe a slot and return how many rows of `rowRem` (+ gap) fit. */
export function useFitRowPageSize(
  slotRef: RefObject<HTMLElement | null>,
  opts: { rowRem: number; gapRem: number; fallback: number },
) {
  const [pageSize, setPageSize] = useState(opts.fallback)

  useEffect(() => {
    const node = slotRef.current
    if (!node) return
    const el: HTMLElement = node

    function measure() {
      if (!el.isConnected) return
      const rem =
        Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
      setPageSize(
        fitRowPageSize({
          slotHeightPx: el.clientHeight,
          remPx: rem,
          rowRem: opts.rowRem,
          gapRem: opts.gapRem,
        }),
      )
    }

    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    window.addEventListener('resize', measure)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [slotRef, opts.rowRem, opts.gapRem])

  return pageSize
}
