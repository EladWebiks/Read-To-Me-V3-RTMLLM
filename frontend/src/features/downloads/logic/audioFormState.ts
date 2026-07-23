import type { AudioFormState } from './audioModalUtils'
import { defaultVoice } from './audioModalUtils'
import type { DownloadProvider } from '@/features/downloads/types'

export function initialAudioForm(
  chapterNumber: number,
  provider: DownloadProvider,
  serverVoice: string | null,
  rate: number,
): AudioFormState {
  return {
    from: chapterNumber,
    to: chapterNumber,
    provider,
    voice: defaultVoice(provider, serverVoice),
    rate,
  }
}

export function applyAudioFormPatch(
  prev: AudioFormState,
  next: Partial<AudioFormState>,
  serverVoice: string | null,
): AudioFormState {
  const provider = next.provider ?? prev.provider
  const voice =
    next.voice ?? (next.provider ? defaultVoice(provider, serverVoice) : prev.voice)
  return { ...prev, ...next, voice }
}
