import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type AssistantPosition = { x: number; y: number }

type AssistantState = {
  open: boolean
  expanded: boolean
  /** Top-left of the floating window; null = default bottom-right placement. */
  position: AssistantPosition | null
  setOpen: (open: boolean) => void
  toggle: () => void
  setExpanded: (expanded: boolean) => void
  toggleExpanded: () => void
  setPosition: (position: AssistantPosition) => void
  resetPosition: () => void
}

export const useAssistantStore = create<AssistantState>()(
  persist(
    (set) => ({
      open: false,
      expanded: false,
      position: null,
      setOpen: (open) => set({ open, ...(open ? {} : { expanded: false }) }),
      toggle: () =>
        set((s) => ({
          open: !s.open,
          ...(s.open ? { expanded: false } : {}),
        })),
      setExpanded: (expanded) => set({ expanded }),
      toggleExpanded: () => set((s) => ({ expanded: !s.expanded })),
      setPosition: (position) => set({ position }),
      resetPosition: () => set({ position: null }),
    }),
    {
      name: 'rtm-assistant-shell',
      partialize: (s) => ({
        expanded: s.expanded,
        position: s.position,
      }),
    },
  ),
)
