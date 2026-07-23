import { useQuery } from '@tanstack/react-query'
import { listServerVoices } from '@/features/reader/api/audioApi'
import type { TtsProviderName } from './ttsSettingsStore'

export function useServerVoices(provider: TtsProviderName) {
  return useQuery({
    queryKey: ['audio', 'voices'],
    queryFn: listServerVoices,
    select: (voices) => voices.filter((voice) => voice.provider === provider),
  })
}
