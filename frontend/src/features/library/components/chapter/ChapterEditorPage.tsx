import { type FormEvent, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { ChevronLeft } from 'lucide-react'
import { Button, Input, Label } from '@/shared/ui'
import { useChapter, useUpdateChapter } from '@/features/library/hooks'

export function ChapterEditorPage() {
  const { bookId = '', chapterId = '' } = useParams()
  const navigate = useNavigate()
  const chapterQuery = useChapter(chapterId)
  const updateChapter = useUpdateChapter(bookId)

  if (chapterQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading chapter…</p>
  }
  if (chapterQuery.isError || !chapterQuery.data) {
    return <p className="text-sm text-destructive">Chapter not found.</p>
  }

  return (
    <section className="space-y-4">
      <Link
        to={`/library/books/${bookId}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to book
      </Link>
      <h1 className="text-2xl font-semibold tracking-tight">
        Edit chapter #{chapterQuery.data.chapter_number}
      </h1>
      <ChapterEditorForm
        initialTitle={chapterQuery.data.title}
        initialContent={chapterQuery.data.content}
        isPending={updateChapter.isPending}
        isError={updateChapter.isError}
        onSubmit={(title, content) => {
          updateChapter.mutate(
            { chapterId, input: { title, content } },
            { onSuccess: () => void navigate(`/library/books/${bookId}`) },
          )
        }}
      />
    </section>
  )
}

type FormProps = {
  initialTitle: string
  initialContent: string
  isPending: boolean
  isError: boolean
  onSubmit: (title: string, content: string) => void
}

function ChapterEditorForm(props: FormProps) {
  const [title, setTitle] = useState(props.initialTitle)
  const [content, setContent] = useState(props.initialContent)

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    props.onSubmit(title, content)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="ch-title">Title</Label>
        <Input id="ch-title" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="ch-content">Content</Label>
        <textarea
          id="ch-content"
          className="min-h-80 w-full rounded-md border border-border bg-background px-3 py-2 font-serif text-sm leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          required
        />
      </div>
      {props.isError && <p className="text-sm text-destructive">Save failed.</p>}
      <Button type="submit" size="sm" disabled={props.isPending}>
        {props.isPending ? 'Saving…' : 'Save chapter'}
      </Button>
    </form>
  )
}
