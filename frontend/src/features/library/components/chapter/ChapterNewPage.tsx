import { type FormEvent, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useBook, useChapters, useCreateChapter } from '@/features/library/hooks'
import { libraryBookHref } from '@/features/library/logic/libraryPaths'
import { InlineLoader, QueryState } from '@/shared/ui'
import { ChapterNewFields } from './ChapterNewFields'
import { ChapterNewLayout } from './ChapterNewLayout'
import { useChapterDraft } from './useChapterDraft'
import { useArrowRightSave, useSaveAndNext } from './useChapterNewKeys'

export function ChapterNewPage() {
  const { bookId = '' } = useParams()
  const navigate = useNavigate()
  const bookQuery = useBook(bookId)
  const chaptersQuery = useChapters(bookId)
  const createChapter = useCreateChapter(bookId)
  const draft = useChapterDraft(bookQuery.data, chaptersQuery.data)
  const [savedCount, setSavedCount] = useState(0)
  const [fastCopy, setFastCopy] = useState(true)
  const saveAndNext = useSaveAndNext(createChapter, draft, setSavedCount)
  useArrowRightSave(fastCopy, draft.content, createChapter.isPending, saveAndNext)

  if (bookQuery.isLoading) {
    return (
      <QueryState
        isPending
        loading={<InlineLoader label="Loading…" />}
        errorLabel="Couldn't load the book."
      >
        {null}
      </QueryState>
    )
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    void createChapter.mutateAsync(draft.toCreateInput()).then(() => {
      void navigate(libraryBookHref(bookId))
    })
  }

  return (
    <ChapterNewLayout
      bookTitle={bookQuery.data?.title ?? 'Book'}
      activeNumber={draft.activeNumber}
      savedCount={savedCount}
      onClose={() => void navigate(libraryBookHref(bookId))}
      onSubmit={handleSubmit}
      pending={createChapter.isPending}
      canSave={Boolean(draft.content.trim())}
      onSaveNext={() => void saveAndNext()}
      fields={
        <ChapterNewFields
          chapterNumber={draft.activeNumber}
          setChapterNumber={draft.setChapterNumber}
          title={draft.title}
          setTitle={draft.setTitle}
          content={draft.content}
          setContent={draft.setContent}
          fastCopy={fastCopy}
          setFastCopy={setFastCopy}
        />
      }
    />
  )
}
