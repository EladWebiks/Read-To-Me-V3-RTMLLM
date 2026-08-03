import { useEffect, useState, type RefObject } from 'react'
import { fitTablePageSize } from '@/shared/hooks/fitTablePageSize'

type Opts = {
  rowRem: number
  headerRem: number
  fallback: number
}

/** How many table body rows fit — prefers measured thead/row heights. */
export function useFitTablePageSize(slotRef: RefObject<HTMLElement | null>, opts: Opts) {
  const [pageSize, setPageSize] = useState(opts.fallback)

  useEffect(() => {
    const node = slotRef.current
    if (!node) return
    const el: HTMLElement = node

    function measure() {
      if (!el.isConnected) return
      const rem =
        Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
      const thead = el.querySelector('thead')
      const row = el.querySelector('tbody tr')
      const next = fitTablePageSize({
        slotHeightPx: el.clientHeight,
        headerHeightPx: thead?.getBoundingClientRect().height ?? opts.headerRem * rem,
        rowHeightPx: row?.getBoundingClientRect().height ?? opts.rowRem * rem,
      })
      if (next === 0) return
      setPageSize((prev) => (prev === next ? prev : next))
    }

    measure()
    let timeoutId = 0
    const raf = window.requestAnimationFrame(() => {
      measure()
      timeoutId = window.setTimeout(measure, 250)
    })
    const ro = new ResizeObserver(() => {
      window.requestAnimationFrame(measure)
    })
    ro.observe(el)
    const mo = new MutationObserver(() => {
      window.requestAnimationFrame(measure)
    })
    mo.observe(el, { childList: true, subtree: true })
    window.addEventListener('resize', measure)
    return () => {
      window.cancelAnimationFrame(raf)
      window.clearTimeout(timeoutId)
      ro.disconnect()
      mo.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [slotRef, opts.rowRem, opts.headerRem, opts.fallback])

  return pageSize
}
