import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type SettingsState = {
  fontSize: number
  maxRate: number
  highlightMode: 'word' | 'paragraph' | 'auto'
  /** Reader column width in px (desktop-resizable). */
  readerWidthPx: number
  setFontSize: (size: number) => void
  setMaxRate: (rate: number) => void
  setHighlightMode: (mode: 'word' | 'paragraph' | 'auto') => void
  setReaderWidthPx: (width: number) => void
}

export const useAppSettings = create<SettingsState>()(
  persist(
    (set) => ({
      fontSize: 1.2,
      maxRate: 3.5,
      highlightMode: 'auto',
      readerWidthPx: 720,
      setFontSize: (fontSize) => set({ fontSize }),
      setMaxRate: (maxRate) => set({ maxRate }),
      setHighlightMode: (highlightMode) => set({ highlightMode }),
      setReaderWidthPx: (readerWidthPx) => set({ readerWidthPx }),
    }),
    { name: 'rtm-app-settings' },
  ),
)
