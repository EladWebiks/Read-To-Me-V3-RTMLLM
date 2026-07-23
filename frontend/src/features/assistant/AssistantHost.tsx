import { useEffect } from 'react'
import { TooltipProvider } from '@/shared/ui'
import { useAssistantStore } from './assistantStore'
import { AssistantWindow } from './AssistantWindow'

/** Global floating assistant panel (opened from the navbar). */
export function AssistantHost() {
  const open = useAssistantStore((s) => s.open)
  const expanded = useAssistantStore((s) => s.expanded)
  const setOpen = useAssistantStore((s) => s.setOpen)
  const setExpanded = useAssistantStore((s) => s.setExpanded)

  useEffect(() => {
    if (!open) return
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      if (expanded) setExpanded(false)
      else setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, expanded, setExpanded, setOpen])

  return (
    <TooltipProvider>
      <AssistantWindow />
    </TooltipProvider>
  )
}
