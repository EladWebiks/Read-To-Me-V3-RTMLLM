import { useEffect, useState, type RefObject } from 'react'
import { fitRowPageSize } from '@/shared/hooks/useFitRowPageSize'

type Opts = {
  /** Approximate table body row height in rem. */
  rowRem: number
  /** Space reserved for sticky/static thead inside the slot. */
  headerRem: number
  fallback: number
}

/** How many table body rows fit in a measured slot after reserving thead. */
export function useAdminTablePageSize(
  slotRef: RefObject<HTMLElement | null>,
  opts: Opts,
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
      const usable = Math.max(0, el.clientHeight - opts.headerRem * rem)
      setPageSize(
        fitRowPageSize({
          slotHeightPx: usable,
          remPx: rem,
          rowRem: opts.rowRem,
          gapRem: 0,
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
  }, [slotRef, opts.rowRem, opts.headerRem, opts.fallback])

  return pageSize
}
