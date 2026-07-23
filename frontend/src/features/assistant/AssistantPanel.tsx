import { useAssistantStore } from './assistantStore'
import { AssistantPanelBody } from './AssistantPanelBody'

/** Floating assistant shell with CSS enter/exit (always mounted, no layout cost). */
export function AssistantPanel() {
  const open = useAssistantStore((s) => s.open)
  const setOpen = useAssistantStore((s) => s.setOpen)

  return (
    <div
      className={`fixed right-4 bottom-4 z-[60] flex w-[min(22rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl transition-[opacity,transform] duration-300 ease-out ${
        open
          ? 'translate-y-0 scale-100 opacity-100'
          : 'pointer-events-none translate-y-3 scale-95 opacity-0'
      }`}
      role="dialog"
      aria-label="Assistant"
      aria-hidden={!open}
    >
      <AssistantPanelBody onClose={() => setOpen(false)} />
    </div>
  )
}
