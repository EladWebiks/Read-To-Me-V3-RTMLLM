import { useCallback, useEffect, useRef } from 'react'

const NEAR_BOTTOM_PX = 64

/** Keep a scroller pinned to the bottom unless the user scrolls up. */
export function useStickToBottom(sending: boolean, contentKey: string) {
  const containerRef = useRef<HTMLDivElement>(null)
  const stuckRef = useRef(true)

  const onScroll = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    stuckRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
  }, [])

  const pin = useCallback(() => {
    const el = containerRef.current
    if (!el || !stuckRef.current) return
    el.scrollTop = el.scrollHeight
  }, [])

  useEffect(() => {
    if (sending) stuckRef.current = true
  }, [sending])

  useEffect(pin, [contentKey, pin])
  useFollowContent(containerRef, pin)

  return { containerRef, onScroll }
}

/**
 * Markdown, tool cards and images keep growing after React commits, so a render
 * effect alone lands above the real bottom. Watch the DOM and re-pin.
 */
function useFollowContent(
  containerRef: { current: HTMLDivElement | null },
  pin: () => void,
) {
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const sizes = new ResizeObserver(pin)
    const observeChildren = () => {
      for (const child of Array.from(el.children)) sizes.observe(child)
    }
    const children = new MutationObserver(() => {
      observeChildren()
      pin()
    })
    observeChildren()
    children.observe(el, { childList: true, subtree: true, characterData: true })
    return () => {
      sizes.disconnect()
      children.disconnect()
    }
  }, [containerRef, pin])
}
