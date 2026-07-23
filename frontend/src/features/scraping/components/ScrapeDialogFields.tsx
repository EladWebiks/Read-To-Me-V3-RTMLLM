import type { ReactNode } from 'react'
import { Input, Label } from '@/shared/ui'

type Props = {
  url: string
  setUrl: (v: string) => void
  bookUrl: string
  setBookUrl: (v: string) => void
  maxChapters: string
  setMaxChapters: (v: string) => void
  startingChapter: string
  setStartingChapter: (v: string) => void
}

export function ScrapeDialogFields(p: Props) {
  return (
    <>
      <Labeled id="first-chapter" label="First Chapter URL">
        <Input
          id="first-chapter"
          value={p.url}
          onChange={(e) => p.setUrl(e.target.value)}
          placeholder="https://novelbin.com/b/…/chapter-1"
          required
          autoFocus
        />
        <p className="text-xs text-muted-foreground">
          novelbin · novelfull · freewebnovel · novellunar
        </p>
      </Labeled>
      <Labeled id="book-page" label="Book Page URL (optional)">
        <Input
          id="book-page"
          value={p.bookUrl}
          onChange={(e) => p.setBookUrl(e.target.value)}
          placeholder="For cover + author; auto-derived if empty"
        />
      </Labeled>
      <Labeled id="max-chapters" label="Max Chapters (optional)">
        <Input
          id="max-chapters"
          type="number"
          min={1}
          value={p.maxChapters}
          onChange={(e) => p.setMaxChapters(e.target.value)}
          placeholder="Empty = all"
        />
      </Labeled>
      <Labeled id="starting-chapter" label="Starting Chapter Number (optional)">
        <Input
          id="starting-chapter"
          type="number"
          min={1}
          value={p.startingChapter}
          onChange={(e) => p.setStartingChapter(e.target.value)}
          placeholder="Defaults to 1"
        />
      </Labeled>
    </>
  )
}

function Labeled({
  id,
  label,
  children,
}: {
  id: string
  label: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}
