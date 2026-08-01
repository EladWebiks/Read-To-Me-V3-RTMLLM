import { Download } from 'lucide-react'
import { Button, Select } from '@/shared/ui'
import type { ChapterSummary } from '@/features/library/types'

type Props = {
  chapters: ChapterSummary[]
  chapterId: string
  prevChapterId: string | null
  nextChapterId: string | null
  onNavigate: (chapterId: string) => void
  onDownload: () => void
}

export function ReaderBottomBar(props: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!props.prevChapterId}
        onClick={() => props.prevChapterId && props.onNavigate(props.prevChapterId)}
      >
        Prev
      </Button>
      <Select
        className="min-w-[12rem] flex-1"
        value={props.chapterId}
        aria-label="Chapter list"
        onChange={(event) => props.onNavigate(event.target.value)}
      >
        {props.chapters.map((chapter) => (
          <option key={chapter.id} value={chapter.id}>
            {chapter.chapter_number}. {chapter.title || 'Untitled'}
          </option>
        ))}
      </Select>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!props.nextChapterId}
        onClick={() => props.nextChapterId && props.onNavigate(props.nextChapterId)}
      >
        Next
      </Button>
      <Button
        type="button"
        variant="outline"
        size="icon"
        aria-label="Download audio"
        title="Download audio"
        onClick={props.onDownload}
      >
        <Download className="h-4 w-4" />
      </Button>
    </div>
  )
}
