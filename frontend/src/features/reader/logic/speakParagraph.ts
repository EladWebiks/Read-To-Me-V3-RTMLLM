import { buildUtterance, charIndexToWordIndex, paragraphText } from './speech'
import type { SpeechStatus } from '@/features/reader/hooks/useSpeech'
import type { ReaderCursor } from '@/features/reader/types'

export type SpeakArgs = {
  paragraphs: string[][]
  rate: number
  volume: number
  voice: SpeechSynthesisVoice | null
  onCursor: (cursor: ReaderCursor) => void
  onChapterEnd: () => void
}

type ArgsRef = { current: SpeakArgs }
type CursorRef = { current: ReaderCursor }
type GenRef = { current: number }

export function speakParagraph(
  paragraphIndex: number,
  wordIndex: number,
  argsRef: ArgsRef,
  cursorRef: CursorRef,
  setStatus: (status: SpeechStatus) => void,
  generation: number,
  genRef: GenRef,
): void {
  if (genRef.current !== generation) return
  const { paragraphs, rate, volume, voice, onCursor, onChapterEnd } = argsRef.current
  const words = paragraphs[paragraphIndex]
  if (!words || words.length === 0) {
    onChapterEnd()
    setStatus('idle')
    return
  }
  const startWord = Math.min(Math.max(wordIndex, 0), words.length - 1)
  const slice = words.slice(startWord)
  const utterance = buildUtterance({
    text: paragraphText(slice),
    rate,
    volume,
    voice,
  })
  wireUtterance(
    utterance,
    paragraphIndex,
    startWord,
    slice,
    argsRef,
    cursorRef,
    setStatus,
    generation,
    genRef,
  )
  if (genRef.current !== generation) return
  setStatus('playing')
  onCursor({ paragraphIndex, wordIndex: startWord })
  window.speechSynthesis.speak(utterance)
}

function wireUtterance(
  utterance: SpeechSynthesisUtterance,
  paragraphIndex: number,
  startWord: number,
  slice: string[],
  argsRef: ArgsRef,
  cursorRef: CursorRef,
  setStatus: (status: SpeechStatus) => void,
  generation: number,
  genRef: GenRef,
): void {
  utterance.onboundary = (event: SpeechSynthesisEvent) => {
    if (genRef.current !== generation) return
    if (event.name !== 'word' && event.name !== '') return
    const relative = charIndexToWordIndex(slice, event.charIndex)
    const next = { paragraphIndex, wordIndex: startWord + relative }
    cursorRef.current = next
    argsRef.current.onCursor(next)
  }
  utterance.onend = () => {
    if (genRef.current !== generation) return
    const nextParagraph = paragraphIndex + 1
    if (nextParagraph >= argsRef.current.paragraphs.length) {
      setStatus('idle')
      argsRef.current.onChapterEnd()
      return
    }
    const next = { paragraphIndex: nextParagraph, wordIndex: 0 }
    cursorRef.current = next
    argsRef.current.onCursor(next)
    speakParagraph(nextParagraph, 0, argsRef, cursorRef, setStatus, generation, genRef)
  }
  utterance.onerror = () => {
    // cancel() raises "interrupted"; ignore so a new play can take over
    if (genRef.current !== generation) return
    setStatus('idle')
  }
}
