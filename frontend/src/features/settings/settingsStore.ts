import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type RegexCutRule = {
  id: string
  pattern: string
  enabled: boolean
}

type SettingsState = {
  fontSize: number
  maxRate: number
  highlightMode: 'word' | 'paragraph' | 'auto'
  /** Reader column width in px (desktop-resizable). */
  readerWidthPx: number
  /** Frontend-only regex rules that cut (remove) matching parts from reader text. */
  regexCutRules: RegexCutRule[]
  setFontSize: (size: number) => void
  setMaxRate: (rate: number) => void
  setHighlightMode: (mode: 'word' | 'paragraph' | 'auto') => void
  setReaderWidthPx: (width: number) => void
  addRegexCutRule: (pattern: string) => void
  removeRegexCutRule: (id: string) => void
  toggleRegexCutRule: (id: string) => void
  clearRegexCutRules: () => void
}

export const useAppSettings = create<SettingsState>()(
  persist(
    (set) => ({
      fontSize: 1.2,
      maxRate: 3.5,
      highlightMode: 'auto',
      readerWidthPx: 720,
      regexCutRules: [],
      setFontSize: (fontSize) => set({ fontSize }),
      setMaxRate: (maxRate) => set({ maxRate }),
      setHighlightMode: (highlightMode) => set({ highlightMode }),
      setReaderWidthPx: (readerWidthPx) => set({ readerWidthPx }),
      addRegexCutRule: (pattern) =>
        set((s) => ({
          regexCutRules: [
            ...s.regexCutRules,
            { id: crypto.randomUUID(), pattern: pattern.trim(), enabled: true },
          ],
        })),
      removeRegexCutRule: (id) =>
        set((s) => ({
          regexCutRules: s.regexCutRules.filter((r) => r.id !== id),
        })),
      toggleRegexCutRule: (id) =>
        set((s) => ({
          regexCutRules: s.regexCutRules.map((r) =>
            r.id === id ? { ...r, enabled: !(r.enabled ?? true) } : r,
          ),
        })),
      clearRegexCutRules: () => set({ regexCutRules: [] }),
    }),
    {
      name: 'rtm-app-settings',
      version: 1,
      migrate: (persisted) => {
        const state = persisted as SettingsState
        if (!state.regexCutRules?.length) return state
        return {
          ...state,
          regexCutRules: state.regexCutRules.map((r) => ({
            id: r.id,
            pattern: r.pattern,
            enabled: 'enabled' in r ? Boolean(r.enabled) : true,
          })),
        }
      },
    },
  ),
)
