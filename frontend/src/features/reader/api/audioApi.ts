import { apiGet, apiPostBlob } from '@/shared/lib/api'
import type { TtsProviderName } from '@/features/reader/hooks/ttsSettingsStore'

export type ServerVoice = {
  provider: TtsProviderName
  id: string
  name: string
  locale: string | null
}

export function listServerVoices(): Promise<ServerVoice[]> {
  return apiGet<ServerVoice[]>('/api/audio/voices')
}

export function synthesizeParagraph(input: {
  text: string
  provider: TtsProviderName
  voice: string | null
  rate: number
}): Promise<Blob> {
  return apiPostBlob('/api/audio/synthesize', {
    text: input.text,
    provider: input.provider,
    voice: input.voice,
    rate: input.rate,
  })
}
