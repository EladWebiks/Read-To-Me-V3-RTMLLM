import { create } from 'zustand'
import type { JobEvent } from './api/streamJobEvents'

type Listener = (event: JobEvent) => void

type JobEventsState = {
  /** True while the multiplex job SSE stream is healthy. */
  connected: boolean
  setConnected: (connected: boolean) => void
  subscribe: (listener: Listener) => () => void
  emit: (event: JobEvent) => void
}

const listeners = new Set<Listener>()

/** Shared flag so job query hooks can fall back to polling when SSE is down. */
export const useJobEventsStore = create<JobEventsState>((set) => ({
  connected: false,
  setConnected: (connected) => set({ connected }),
  subscribe: (listener) => {
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  },
  emit: (event) => {
    for (const listener of listeners) listener(event)
  },
}))
