import { useCallback, useEffect } from 'react'
import type { useCreateChapter } from '@/features/library/hooks'
import type { useChapterDraft } from './useChapterDraft'

export function useSaveAndNext(
  createChapter: ReturnType<typeof useCreateChapter>,
  draft: ReturnType<typeof useChapterDraft>,
  setSavedCount: (fn: (n: number) => number) => void,
) {
  return useCallback(async () => {
    await createChapter.mutateAsync(draft.toCreateInput())
    setSavedCount((n) => n + 1)
    draft.resetForNext()
  }, [createChapter, draft, setSavedCount])
}

export function useArrowRightSave(
  enabled: boolean,
  content: string,
  pending: boolean,
  saveAndNext: () => Promise<void>,
) {
  useEffect(() => {
    if (!enabled) return
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'ArrowRight' || !content.trim() || pending) return
      event.preventDefault()
      void saveAndNext()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled, content, pending, saveAndNext])
}
