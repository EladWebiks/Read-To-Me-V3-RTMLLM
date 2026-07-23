import { type FormEvent, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'
import { uploadCover } from '@/features/library/api'
import { booksQueryKey, useCreateBook } from '@/features/library/hooks'
import type { Book } from '@/features/library/types'
import { BookFormFields } from './BookFormFields'

type Props = {
  open: boolean
  onClose: () => void
  book?: Book | null
}

export function BookFormDialog({ open, onClose, book }: Props) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        {open ? (
          <BookFormBody key={book?.id ?? 'new'} book={book ?? null} onClose={onClose} />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function BookFormBody({ book, onClose }: { book: Book | null; onClose: () => void }) {
  const create = useCreateBook()
  const queryClient = useQueryClient()
  const [title, setTitle] = useState(book?.title ?? '')
  const [author, setAuthor] = useState(book?.author ?? '')
  const [starting, setStarting] = useState(String(book?.starting_chapter_number ?? 1))
  const [coverFile, setCoverFile] = useState<File | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    const created = await create.mutateAsync({
      title: title.trim(),
      author: author.trim(),
      starting_chapter_number: Number(starting) || 1,
    })
    if (coverFile) {
      await uploadCover(created.id, coverFile)
      void queryClient.invalidateQueries({ queryKey: booksQueryKey })
    }
    onClose()
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
      <DialogHeader>
        <DialogTitle>{book ? 'Edit Book' : 'New Book'}</DialogTitle>
      </DialogHeader>
      <BookFormFields
        title={title}
        setTitle={setTitle}
        author={author}
        setAuthor={setAuthor}
        starting={starting}
        setStarting={setStarting}
        showStarting={!book}
        onCoverChange={setCoverFile}
      />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={create.isPending || !title.trim()}>
          {create.isPending ? 'Saving…' : book ? 'Save' : 'Create'}
        </Button>
      </div>
    </form>
  )
}
