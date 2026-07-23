import { useEffect, useState, type RefObject } from 'react'
import { fitLibraryPageSize } from '@/features/library/logic/fitLibraryPageSize'

const FALLBACK_PAGE_SIZE = 6

/** Observe the grid slot and return how many cards fit without scrolling. */
export function useFitLibraryPageSize(slotRef: RefObject<HTMLElement | null>) {
  const [pageSize, setPageSize] = useState(FALLBACK_PAGE_SIZE)

  useEffect(() => {
    const node = slotRef.current
    if (!node) return
    const el: HTMLElement = node

    function measure() {
      if (!el.isConnected) return
      const rem =
        Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
      setPageSize(
        fitLibraryPageSize({
          gridHeightPx: el.clientHeight,
          viewportWidth: window.innerWidth,
          remPx: rem,
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
  }, [slotRef])

  return pageSize
}
