import type {
  PlaybackEngine,
  TtsProviderName,
} from '@/features/reader/hooks/ttsSettingsStore'
import type { ServerVoice } from '@/features/reader/api/audioApi'

export type PlayerControlsProps = {
  engine: PlaybackEngine
  provider: TtsProviderName
  browserVoices: SpeechSynthesisVoice[]
  serverVoices: ServerVoice[]
  voiceURI: string | null
  serverVoice: string | null
  rate: number
  volume: number
  autoNext: boolean
  onEngine: (engine: PlaybackEngine) => void
  onProvider: (provider: TtsProviderName) => void
  onVoice: (voiceURI: string | null) => void
  onServerVoice: (voice: string | null) => void
  onRate: (rate: number) => void
  onVolume: (volume: number) => void
  onAutoNext: (autoNext: boolean) => void
}
