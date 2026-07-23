import { useServerSpeech } from './useServerSpeech'
import { useServerVoices } from './useServerVoices'
import { useSpeech } from './useSpeech'
import { useVoices } from './useVoices'
import type { PlaybackEngine, TtsProviderName } from './ttsSettingsStore'
import type { ReaderCursor } from '@/features/reader/types'

type SettingsSlice = {
  engine: PlaybackEngine
  provider: TtsProviderName
  voiceURI: string | null
  serverVoice: string | null
  rate: number
  volume: number
}

type PlaybackArgs = {
  paragraphs: string[][]
  settings: SettingsSlice
  onCursor: (cursor: ReaderCursor) => void
  onChapterEnd: () => void
}

export function usePlaybackEngine({
  paragraphs,
  settings,
  onCursor,
  onChapterEnd,
}: PlaybackArgs) {
  const browserVoices = useVoices()
  const serverVoices = useServerVoices(settings.provider)
  const browserVoice =
    browserVoices.find((item) => item.voiceURI === settings.voiceURI) ?? null
  const browser = useSpeech({
    paragraphs,
    rate: settings.rate,
    volume: settings.volume,
    voice: browserVoice,
    onCursor,
    onChapterEnd,
  })
  const server = useServerSpeech({
    paragraphs,
    provider: settings.provider,
    voice: settings.serverVoice,
    rate: settings.rate,
    volume: settings.volume,
    onCursor,
    onChapterEnd,
  })
  return {
    speech: settings.engine === 'server' ? server : browser,
    error: settings.engine === 'server' ? server.error : null,
    browserVoices,
    serverVoices: serverVoices.data ?? [],
  }
}
