import { useRef } from 'react'
import { useFitTablePageSize } from '@/shared/hooks/useFitTablePageSize'
import { useViewportLock } from '@/shared/hooks/useViewportLock'

type Opts = {
  rowRem: number
  headerRem: number
  fallback: number
}

/** Viewport-lock a list section and measure how many table rows fit in the slot. */
export function useDataListLayout(opts: Opts) {
  const sectionRef = useRef<HTMLElement>(null)
  const slotRef = useRef<HTMLDivElement>(null)
  useViewportLock(sectionRef)
  const pageSize = useFitTablePageSize(slotRef, opts)
  return { sectionRef, slotRef, pageSize }
}
