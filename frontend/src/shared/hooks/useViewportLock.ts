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
      section.style.height = `${Math.max(280, window.innerHeight - top - padBottom)}px`
    }

    sync()
    window.addEventListener('resize', sync)
    return () => window.removeEventListener('resize', sync)
  }, [sectionRef])
}
