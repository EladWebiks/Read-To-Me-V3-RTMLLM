import { type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ChevronLeft } from 'lucide-react'
import { Button } from '@/shared/ui'

type Props = {
  bookTitle: string
  activeNumber: string
  savedCount: number
  onClose: () => void
  onSubmit: (e: FormEvent) => void
  pending: boolean
  canSave: boolean
  onSaveNext: () => void
  fields: ReactNode
}

export function ChapterNewLayout(props: Props) {
  return (
    <section className="mx-auto max-w-3xl space-y-4 animate-fade-in-up">
      <Link
        to="/library"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to Library
      </Link>
      <h1 className="text-2xl font-semibold tracking-tight">
        {props.bookTitle} — Add Chapter #{props.activeNumber}
      </h1>
      {props.savedCount > 0 ? (
        <p className="text-sm text-muted-foreground">
          {props.savedCount} chapter(s) saved this session
        </p>
      ) : null}
      <form onSubmit={props.onSubmit} className="space-y-3">
        {props.fields}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={props.onClose}>
            Close
          </Button>
          <Button type="submit" disabled={props.pending || !props.canSave}>
            {props.pending ? 'Saving…' : 'Save & Close'}
          </Button>
          <Button
            type="button"
            disabled={props.pending || !props.canSave}
            onClick={props.onSaveNext}
          >
            Save &amp; Next
          </Button>
        </div>
      </form>
    </section>
  )
}
