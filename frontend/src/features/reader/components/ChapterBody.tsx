import { useEffect, useRef, type CSSProperties } from 'react'
import { useAppSettings } from '@/features/settings/settingsStore'
import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'

type Cursor = { paragraphIndex: number; wordIndex: number }

type ChapterBodyProps = {
  paragraphs: string[][]
  activeCursor: Cursor
  onWordClick: (cursor: Cursor) => void
}

export function ChapterBody({ paragraphs, activeCursor, onWordClick }: ChapterBodyProps) {
  const { fontSize, highlightMode } = useAppSettings()
  const engine = useTtsSettings((s) => s.engine)
  const activeRef = useRef<HTMLParagraphElement>(null)
  const prevParagraph = useRef(activeCursor.paragraphIndex)

  const useParagraphHL =
    highlightMode === 'paragraph' || (highlightMode === 'auto' && engine === 'server')

  useEffect(() => {
    if (activeCursor.paragraphIndex !== prevParagraph.current) {
      prevParagraph.current = activeCursor.paragraphIndex
      activeRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [activeCursor.paragraphIndex])

  if (paragraphs.length === 0) {
    return <p className="text-muted-foreground">This chapter has no content.</p>
  }

  const style = { '--reader-font-size': `${fontSize}rem` } as CSSProperties

  return (
    <article className="reader-prose" style={style}>
      {paragraphs.map((words, pIdx) => (
        <Paragraph
          key={pIdx}
          ref={pIdx === activeCursor.paragraphIndex ? activeRef : null}
          words={words}
          pIdx={pIdx}
          activeCursor={activeCursor}
          paragraphHL={useParagraphHL}
          onWordClick={onWordClick}
        />
      ))}
    </article>
  )
}

import { forwardRef } from 'react'

type ParagraphProps = {
  words: string[]
  pIdx: number
  activeCursor: Cursor
  paragraphHL: boolean
  onWordClick: (cursor: Cursor) => void
}

const Paragraph = forwardRef<HTMLParagraphElement, ParagraphProps>(function Paragraph(
  { words, pIdx, activeCursor, paragraphHL, onWordClick },
  ref,
) {
  const isActive = pIdx === activeCursor.paragraphIndex
  const cls = isActive && paragraphHL ? 'reader-paragraph-active' : undefined
  return (
    <p ref={ref} className={cls}>
      {words.map((word, wIdx) => {
        const wordActive = isActive && wIdx === activeCursor.wordIndex && !paragraphHL
        return (
          <span key={`${pIdx}-${wIdx}`}>
            {wIdx > 0 ? ' ' : null}
            <button
              type="button"
              className={wordActive ? 'reader-word reader-word-active' : 'reader-word'}
              onClick={() => onWordClick({ paragraphIndex: pIdx, wordIndex: wIdx })}
            >
              {word}
            </button>
          </span>
        )
      })}
    </p>
  )
})
