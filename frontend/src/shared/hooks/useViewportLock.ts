import { useEffect, type RefObject } from 'react'

/** Pin an element to the remaining viewport under the sticky shell header. */
export function useViewportLock(sectionRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const node = sectionRef.current
    if (!node) return
    const section: HTMLElement = node

    function sync() {
      const top = section.getBoundingClientRect().top
      const main = section.closest('main')
      const padBottom = main
        ? Number.parseFloat(getComputedStyle(main).paddingBottom) || 0
        : 16
      const next = `${Math.max(280, window.innerHeight - top - padBottom)}px`
      if (section.style.height !== next) section.style.height = next
    }

    sync()
    // Re-measure after paint + entrance animation (translateY shifts getBoundingClientRect).
    let timeoutId = 0
    const raf = window.requestAnimationFrame(() => {
      sync()
      timeoutId = window.setTimeout(sync, 250)
    })
    window.addEventListener('resize', sync)
    window.visualViewport?.addEventListener('resize', sync)
    return () => {
      window.cancelAnimationFrame(raf)
      window.clearTimeout(timeoutId)
      window.removeEventListener('resize', sync)
      window.visualViewport?.removeEventListener('resize', sync)
      section.style.height = ''
    }
  }, [sectionRef])
}
