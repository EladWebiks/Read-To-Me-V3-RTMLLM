import type { MouseEvent, ReactNode } from 'react'
import { Pencil, Play, Trash2 } from 'lucide-react'
import { Button } from '@/shared/ui'
import type { Book } from '@/features/library/types'

type Props = {
  book: Book
  onEdit: (book: Book) => void
  onRead: (book: Book) => void
  onDelete: (bookId: string) => void
  isDeleting: boolean
}

export function BookCardActions(props: Props) {
  const { book, onEdit, onRead, onDelete, isDeleting } = props
  function stop(event: MouseEvent) {
    event.stopPropagation()
  }
  return (
    <div className="flex shrink-0 items-center gap-0.5" onClick={stop}>
      <IconBtn
        label={`Edit ${book.title}`}
        title="Edit book"
        onClick={() => onEdit(book)}
      >
        <Pencil className="h-3.5 w-3.5" />
      </IconBtn>
      {book.chapter_count > 0 ? (
        <IconBtn label={`Read ${book.title}`} title="Read" onClick={() => onRead(book)}>
          <Play className="h-3.5 w-3.5 fill-current" />
        </IconBtn>
      ) : null}
      <IconBtn
        label={`Delete ${book.title}`}
        title="Delete"
        disabled={isDeleting}
        danger
        onClick={() => onDelete(book.id)}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </IconBtn>
    </div>
  )
}

function IconBtn(props: {
  label: string
  title: string
  onClick: () => void
  disabled?: boolean
  danger?: boolean
  children: ReactNode
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={
        props.danger
          ? 'h-8 w-8 cursor-pointer text-destructive hover:bg-destructive/10 hover:text-destructive'
          : 'h-8 w-8 cursor-pointer'
      }
      aria-label={props.label}
      title={props.title}
      disabled={props.disabled}
      onClick={props.onClick}
    >
      {props.children}
    </Button>
  )
}
