import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import { useAppSettings } from '@/features/settings/settingsStore'
import type { UiSettingsPatch } from '../api/chatTypes'
import { applySettingsPatch } from './settingsActions'

describe('applySettingsPatch', () => {
  beforeEach(() => {
    useAppSettings.setState({ fontSize: 1.2, maxRate: 3.5, highlightMode: 'auto' })
    useTtsSettings.setState({
      engine: 'browser',
      provider: 'edge',
      voiceURI: null,
      serverVoice: null,
      rate: 1,
    })
  })

  it('applies allowlisted website and server voice settings', () => {
    const setTheme = vi.fn()
    applySettingsPatch(
      {
        theme: 'dark',
        font_size: 1.45,
        playback_rate: 3.8,
        tts_provider: 'sapi',
        voice: 'Microsoft David',
        highlighting: 'paragraph',
      },
      setTheme,
    )

    expect(setTheme).toHaveBeenCalledWith('dark')
    expect(useAppSettings.getState().fontSize).toBe(1.45)
    expect(useAppSettings.getState().maxRate).toBe(3.8)
    expect(useAppSettings.getState().highlightMode).toBe('paragraph')
    expect(useTtsSettings.getState().engine).toBe('server')
    expect(useTtsSettings.getState().provider).toBe('sapi')
    expect(useTtsSettings.getState().serverVoice).toBe('Microsoft David')
  })

  it('ignores invalid values received at runtime', () => {
    const patch = { theme: 'neon', font_size: 9 } as unknown as UiSettingsPatch
    applySettingsPatch(patch, vi.fn())

    expect(useAppSettings.getState().fontSize).toBe(1.2)
  })
})
