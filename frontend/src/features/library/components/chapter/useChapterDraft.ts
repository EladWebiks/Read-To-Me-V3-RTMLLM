import { useMemo, useState } from 'react'
import type { Book, ChapterSummary } from '@/features/library/types'

export function useChapterDraft(
  book: Book | undefined,
  chapters: ChapterSummary[] | undefined,
) {
  const suggested = useMemo(
    () => nextChapterNumber(book?.starting_chapter_number ?? 1, chapters ?? []),
    [book?.starting_chapter_number, chapters],
  )
  const [chapterNumber, setChapterNumber] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const activeNumber = chapterNumber || String(suggested)

  return {
    activeNumber,
    title,
    content,
    setChapterNumber,
    setTitle,
    setContent,
    toCreateInput: () => ({
      title: title.trim() || undefined,
      content,
      chapter_number: Number(activeNumber) || suggested,
    }),
    resetForNext: () => {
      const num = Number(activeNumber) || suggested
      setTitle('')
      setContent('')
      setChapterNumber(String(num + 1))
    },
  }
}

function nextChapterNumber(
  starting: number,
  chapters: { chapter_number: number }[],
): number {
  if (chapters.length === 0) return starting
  return Math.max(...chapters.map((c) => c.chapter_number)) + 1
}
