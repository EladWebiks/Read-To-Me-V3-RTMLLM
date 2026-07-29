import { Button, Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'
import type { Book } from '@/features/library/types'

type Props = {
  book: Book | null
  open: boolean
  busy: boolean
  onClose: () => void
  onConfirm: () => void
}

/** Confirm destructive book delete (chapters go with it). */
export function DeleteBookModal({ book, open, busy, onClose, onConfirm }: Props) {
  const chapters = book?.chapter_count ?? 0
  const chapterLabel =
    chapters === 1 ? '1 associated chapter' : `${chapters} associated chapters`

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !busy && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete book?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          {book ? (
            <>
              Delete <span className="font-medium text-foreground">{book.title}</span>?
              This will permanently remove the book and all {chapterLabel}.
            </>
          ) : null}
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            disabled={busy || !book}
            onClick={onConfirm}
          >
            {busy ? 'Deleting…' : 'Delete'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
