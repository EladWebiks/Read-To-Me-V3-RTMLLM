import { describe, expect, it } from 'vitest'
import { applyAudioFormPatch, initialAudioForm } from './audioFormState'

describe('audio form defaults', () => {
  it('uses 1.35 for Zira even when the saved playback rate differs', () => {
    const form = initialAudioForm(3, 'sapi', null, 2)

    expect(form.voice).toBe('Microsoft Zira Desktop')
    expect(form.rate).toBe(1.35)
  })

  it('applies the Zira rate when switching to SAPI', () => {
    const edge = initialAudioForm(3, 'edge', 'en-US-AvaNeural', 2)
    const sapi = applyAudioFormPatch(edge, { provider: 'sapi' }, null, 2)

    expect(sapi.voice).toBe('Microsoft Zira Desktop')
    expect(sapi.rate).toBe(1.35)
  })

  it('keeps an explicitly selected rate', () => {
    const form = initialAudioForm(3, 'sapi', null, 2)
    const changed = applyAudioFormPatch(form, { rate: 1.6 }, null, 2)

    expect(changed.rate).toBe(1.6)
  })
})
