import { useEffect, useRef } from 'react'

const NEAR_BOTTOM_PX = 64

/** Keep a scroller pinned to the bottom unless the user scrolls up. */
export function useStickToBottom(sending: boolean, contentKey: string) {
  const containerRef = useRef<HTMLDivElement>(null)
  const stuckRef = useRef(true)

  const onScroll = () => {
    const el = containerRef.current
    if (!el) return
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    stuckRef.current = distance < NEAR_BOTTOM_PX
  }

  const scrollToBottom = () => {
    const el = containerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }

  useEffect(() => {
    if (sending) stuckRef.current = true
  }, [sending])

  useEffect(() => {
    if (stuckRef.current || sending) scrollToBottom()
  }, [contentKey, sending])

  return { containerRef, onScroll }
}
