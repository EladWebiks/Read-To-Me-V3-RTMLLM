import { type FormEvent, useState } from 'react'
import { Button, Card, Input, Label } from '@/shared/ui'
import { useCreateChapter } from '@/features/library/hooks'

type AddChapterFormProps = { bookId: string }

export function AddChapterForm({ bookId }: AddChapterFormProps) {
  const createChapter = useCreateChapter(bookId)
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)} size="sm">
        Add chapter
      </Button>
    )
  }

  return (
    <AddChapterFields
      isPending={createChapter.isPending}
      onCancel={() => setOpen(false)}
      onSubmit={(title, content) => {
        createChapter.mutate({ title, content }, { onSuccess: () => setOpen(false) })
      }}
    />
  )
}

type FieldProps = {
  isPending: boolean
  onCancel: () => void
  onSubmit: (title: string, content: string) => void
}

function AddChapterFields({ isPending, onCancel, onSubmit }: FieldProps) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    onSubmit(title, content)
  }

  return (
    <Card className="p-4">
      <form onSubmit={handleSubmit} className="space-y-3">
        <h2 className="font-medium">New chapter</h2>
        <div className="space-y-1">
          <Label htmlFor="ch-title">Title</Label>
          <Input id="ch-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="ch-content">Content</Label>
          <textarea
            id="ch-content"
            className="min-h-40 w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            required
          />
        </div>
        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={isPending}>
            {isPending ? 'Saving…' : 'Save'}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  )
}
