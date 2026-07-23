import { Input, Label } from '@/shared/ui'

type Props = {
  chapterNumber: string
  setChapterNumber: (v: string) => void
  title: string
  setTitle: (v: string) => void
  content: string
  setContent: (v: string) => void
  fastCopy: boolean
  setFastCopy: (v: boolean) => void
}

export function ChapterNewFields(props: Props) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="ch-num">Chapter number</Label>
        <Input
          id="ch-num"
          type="number"
          min={0}
          value={props.chapterNumber}
          onChange={(e) => props.setChapterNumber(e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ch-title">Title (optional)</Label>
        <Input
          id="ch-title"
          value={props.title}
          onChange={(e) => props.setTitle(e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ch-content">Content</Label>
        <textarea
          id="ch-content"
          className="min-h-80 w-full rounded-md border border-input bg-background px-3 py-2 font-serif text-sm leading-relaxed"
          value={props.content}
          onChange={(e) => props.setContent(e.target.value)}
          required
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={props.fastCopy}
          onChange={(e) => props.setFastCopy(e.target.checked)}
        />
        Fast copy: ArrowRight = Save &amp; Next
      </label>
    </>
  )
}
