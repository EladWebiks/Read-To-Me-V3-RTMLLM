import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type AssistantPosition = { x: number; y: number }

type AssistantState = {
  open: boolean
  expanded: boolean
  /** Top-left of the floating window; null = default bottom-right placement. */
  position: AssistantPosition | null
  /** Active server conversation; null starts a new thread on next send. */
  conversationId: string | null
  /** Bumps when the user requests a fresh chat from the header. */
  newChatNonce: number
  setOpen: (open: boolean) => void
  toggle: () => void
  setExpanded: (expanded: boolean) => void
  toggleExpanded: () => void
  setPosition: (position: AssistantPosition) => void
  resetPosition: () => void
  setConversationId: (conversationId: string | null) => void
  requestNewChat: () => void
}

export const useAssistantStore = create<AssistantState>()(
  persist(
    (set) => ({
      open: false,
      expanded: false,
      position: null,
      conversationId: null,
      newChatNonce: 0,
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
      setConversationId: (conversationId) => set({ conversationId }),
      requestNewChat: () =>
        set((s) => ({
          conversationId: null,
          newChatNonce: s.newChatNonce + 1,
        })),
    }),
    {
      name: 'rtm-assistant-shell',
      partialize: (s) => ({
        expanded: s.expanded,
        position: s.position,
        conversationId: s.conversationId,
      }),
    },
  ),
)
