import type { AudioFormState } from './audioModalUtils'
import { defaultDownloadRate, defaultVoice } from './audioModalUtils'
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
    rate: defaultDownloadRate(provider, rate),
  }
}

export function applyAudioFormPatch(
  prev: AudioFormState,
  next: Partial<AudioFormState>,
  serverVoice: string | null,
  savedRate: number,
): AudioFormState {
  const provider = next.provider ?? prev.provider
  const voice =
    next.voice ?? (next.provider ? defaultVoice(provider, serverVoice) : prev.voice)
  const rate =
    next.rate ?? (next.provider ? defaultDownloadRate(provider, savedRate) : prev.rate)
  return { ...prev, ...next, voice, rate }
}
