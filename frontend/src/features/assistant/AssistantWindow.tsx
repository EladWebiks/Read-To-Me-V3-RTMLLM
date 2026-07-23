import { AnimatePresence } from 'motion/react'
import { AssistantShell } from './AssistantShell'
import { useAssistantStore } from './assistantStore'

/** Motion-wrapped open/close for the global assistant window. */
export function AssistantWindow() {
  const open = useAssistantStore((s) => s.open)
  return (
    <AnimatePresence>
      {open ? <AssistantShell key="assistant-shell" /> : null}
    </AnimatePresence>
  )
}
