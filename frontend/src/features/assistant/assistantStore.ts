import { create } from 'zustand'

type AssistantState = {
  open: boolean
  setOpen: (open: boolean) => void
  toggle: () => void
}

export const useAssistantStore = create<AssistantState>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
  toggle: () => set((s) => ({ open: !s.open })),
}))
