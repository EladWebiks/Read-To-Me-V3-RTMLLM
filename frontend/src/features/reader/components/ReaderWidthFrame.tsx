import {
  useCallback,
  useRef,
  useSyncExternalStore,
  type PointerEvent,
  type ReactNode,
  type RefObject,
} from 'react'
import { useAppSettings } from '@/features/settings/settingsStore'

const MIN_W = 480
const MAX_W = 1200

/** Centers the reader at a capped width; desktop edges drag to resize. */
export function ReaderWidthFrame({ children }: { children: ReactNode }) {
  const stored = useAppSettings((s) => s.readerWidthPx)
  const setStored = useAppSettings((s) => s.setReaderWidthPx)
  const viewport = useViewportWidth()
  const frameRef = useRef<HTMLDivElement>(null)
  const onDrag = useWidthDrag(frameRef, setStored)
  const capped = clampWidth(stored, viewport)

  return (
    <div className="flex min-h-0 flex-1 justify-center">
      <div
        ref={frameRef}
        className="relative flex min-h-0 w-full max-w-full flex-1 flex-col md:w-[var(--reader-w)] md:flex-none"
        style={{ ['--reader-w' as string]: `${capped}px` }}
      >
        <WidthHandle side="left" onPointerDown={onDrag} />
        {children}
        <WidthHandle side="right" onPointerDown={onDrag} />
      </div>
    </div>
  )
}

function WidthHandle(props: {
  side: 'left' | 'right'
  onPointerDown: (event: PointerEvent<HTMLButtonElement>, side: 'left' | 'right') => void
}) {
  return (
    <button
      type="button"
      aria-label={`Resize reader (${props.side})`}
      title="Drag to resize width"
      className={`absolute top-0 bottom-0 z-10 hidden w-2 cursor-col-resize touch-none border-0 bg-transparent p-0 md:block ${
        props.side === 'left' ? '-left-1' : '-right-1'
      } hover:bg-primary/15 active:bg-primary/25`}
      onPointerDown={(e) => props.onPointerDown(e, props.side)}
    />
  )
}

function useViewportWidth(): number {
  return useSyncExternalStore(subscribeViewport, getViewport, () => MAX_W)
}

function subscribeViewport(onStoreChange: () => void): () => void {
  window.addEventListener('resize', onStoreChange)
  return () => window.removeEventListener('resize', onStoreChange)
}

function getViewport(): number {
  return window.innerWidth
}

function useWidthDrag(
  frameRef: RefObject<HTMLDivElement | null>,
  setWidth: (w: number) => void,
) {
  return useCallback(
    (event: PointerEvent<HTMLButtonElement>, side: 'left' | 'right') => {
      event.preventDefault()
      const frame = frameRef.current
      if (!frame) return
      const startX = event.clientX
      const startW = frame.getBoundingClientRect().width
      event.currentTarget.setPointerCapture(event.pointerId)

      function onMove(ev: globalThis.PointerEvent) {
        const delta = ev.clientX - startX
        const next = side === 'right' ? startW + delta * 2 : startW - delta * 2
        setWidth(clampWidth(next, window.innerWidth))
      }
      function onUp() {
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
      }
      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
    },
    [frameRef, setWidth],
  )
}

function clampWidth(width: number, viewport: number): number {
  const cap = Math.min(MAX_W, Math.max(MIN_W, viewport - 48))
  return Math.round(Math.min(cap, Math.max(MIN_W, width)))
}
