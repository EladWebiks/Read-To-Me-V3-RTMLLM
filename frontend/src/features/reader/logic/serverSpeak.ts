import { synthesizeParagraph } from '@/features/reader/api/audioApi'
import { playBlob } from './audioDom'
import { paragraphText } from './speech'
import type { SpeechStatus } from '@/features/reader/hooks/useSpeech'
import type { TtsProviderName } from '@/features/reader/hooks/ttsSettingsStore'
import type { ReaderCursor } from '@/features/reader/types'

type Args = {
  paragraphs: string[][]
  provider: TtsProviderName
  voice: string | null
  rate: number
  volume: number
  onCursor: (cursor: ReaderCursor) => void
  onChapterEnd: () => void
  onError?: (message: string) => void
}

type PlayCtx = {
  argsRef: { current: Args }
  audioRef: { current: HTMLAudioElement | null }
  urlRef: { current: string | null }
  settleRef: { current: (() => void) | null }
  setStatus: (status: SpeechStatus) => void
  genRef: { current: number }
  generation: number
}

function isCurrent(ctx: PlayCtx): boolean {
  return ctx.genRef.current === ctx.generation
}

export async function speakParagraphChunk(
  paragraphIndex: number,
  ctx: PlayCtx,
): Promise<void> {
  if (!isCurrent(ctx)) return
  const { paragraphs, onCursor, onChapterEnd } = ctx.argsRef.current
  if (paragraphIndex >= paragraphs.length) {
    ctx.setStatus('idle')
    onChapterEnd()
    return
  }
  const words = paragraphs[paragraphIndex] ?? []
  if (words.length === 0) {
    await speakParagraphChunk(paragraphIndex + 1, ctx)
    return
  }
  onCursor({ paragraphIndex, wordIndex: 0 })
  ctx.setStatus('playing')
  await playParagraph(words, paragraphIndex, ctx)
}

async function playParagraph(
  words: string[],
  paragraphIndex: number,
  ctx: PlayCtx,
): Promise<void> {
  const { argsRef, audioRef, urlRef, settleRef, setStatus } = ctx
  try {
    const blob = await synthesizeParagraph({
      text: paragraphText(words),
      provider: argsRef.current.provider,
      voice: argsRef.current.voice,
      rate: argsRef.current.rate,
    })
    if (!isCurrent(ctx)) return
    const cancelled = { current: false }
    await playBlob(blob, argsRef.current.volume, audioRef, urlRef, settleRef, cancelled)
    if (!isCurrent(ctx)) return
    await speakParagraphChunk(paragraphIndex + 1, ctx)
  } catch (error) {
    if (!isCurrent(ctx)) return
    setStatus('idle')
    const message = error instanceof Error ? error.message : 'TTS failed'
    argsRef.current.onError?.(message)
  }
}
