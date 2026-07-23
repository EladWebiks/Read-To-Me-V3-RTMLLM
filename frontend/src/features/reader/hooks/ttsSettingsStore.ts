import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type PlaybackEngine = 'browser' | 'server'
export type TtsProviderName = 'edge' | 'sapi'

type TtsSettings = {
  engine: PlaybackEngine
  provider: TtsProviderName
  voiceURI: string | null
  serverVoice: string | null
  rate: number
  volume: number
  autoNext: boolean
  setEngine: (engine: PlaybackEngine) => void
  setProvider: (provider: TtsProviderName) => void
  setVoiceURI: (voiceURI: string | null) => void
  setServerVoice: (serverVoice: string | null) => void
  setRate: (rate: number) => void
  setVolume: (volume: number) => void
  setAutoNext: (autoNext: boolean) => void
}

export const useTtsSettings = create<TtsSettings>()(
  persist(
    (set) => ({
      engine: 'browser',
      provider: 'edge',
      voiceURI: null,
      serverVoice: null,
      rate: 1,
      volume: 1,
      autoNext: true,
      setEngine: (engine) => set({ engine }),
      setProvider: (provider) => set({ provider, serverVoice: null }),
      setVoiceURI: (voiceURI) => set({ voiceURI }),
      setServerVoice: (serverVoice) => set({ serverVoice }),
      setRate: (rate) => set({ rate }),
      setVolume: (volume) => set({ volume }),
      setAutoNext: (autoNext) => set({ autoNext }),
    }),
    { name: 'rtm-tts' },
  ),
)
