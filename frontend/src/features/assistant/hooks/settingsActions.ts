import type { UiSettingsPatch } from '../api/chatTypes'
import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import { useAppSettings } from '@/features/settings/settingsStore'

type SetTheme = (theme: 'light' | 'dark' | 'system') => void

/** Revalidate and apply only allowlisted reversible settings. */
export function applySettingsPatch(patch: UiSettingsPatch, setTheme: SetTheme): void {
  applyAppSettings(patch, setTheme)
  applyTtsSettings(patch)
}

function applyAppSettings(patch: UiSettingsPatch, setTheme: SetTheme): void {
  const app = useAppSettings.getState()
  if (isOneOf(patch.theme, ['light', 'dark', 'system'])) setTheme(patch.theme)
  if (inRange(patch.font_size, 1, 1.8)) app.setFontSize(patch.font_size)
  if (inRange(patch.max_playback_rate, 1, 4)) app.setMaxRate(patch.max_playback_rate)
  if (isOneOf(patch.highlighting, ['auto', 'word', 'paragraph'])) {
    app.setHighlightMode(patch.highlighting)
  }
}

function applyTtsSettings(patch: UiSettingsPatch): void {
  const app = useAppSettings.getState()
  const tts = useTtsSettings.getState()
  if (inRange(patch.max_playback_rate, 1, 4) && tts.rate > patch.max_playback_rate) {
    tts.setRate(patch.max_playback_rate)
  }
  if (inRange(patch.playback_rate, 0.5, 4)) {
    if (patch.playback_rate > app.maxRate) app.setMaxRate(patch.playback_rate)
    tts.setRate(patch.playback_rate)
  }
  if (isOneOf(patch.playback_engine, ['browser', 'server'])) {
    tts.setEngine(patch.playback_engine)
  }
  if (isOneOf(patch.tts_provider, ['edge', 'sapi'])) {
    tts.setEngine('server')
    tts.setProvider(patch.tts_provider)
  }
  if (typeof patch.voice === 'string' && patch.voice.length <= 200) {
    const engine = useTtsSettings.getState().engine
    if (engine === 'server') tts.setServerVoice(patch.voice || null)
    else tts.setVoiceURI(patch.voice || null)
  }
}

function inRange(value: unknown, min: number, max: number): value is number {
  return (
    typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max
  )
}

function isOneOf<T extends string>(value: unknown, allowed: readonly T[]): value is T {
  return typeof value === 'string' && allowed.includes(value as T)
}
