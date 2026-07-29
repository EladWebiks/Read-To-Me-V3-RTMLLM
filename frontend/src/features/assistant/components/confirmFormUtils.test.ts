import { describe, expect, it } from 'vitest'
import type { ConfirmationPayload } from '../api/chatApi'
import { defaultsFrom } from './confirmFormUtils'

function audioPayload(provided: Partial<Record<string, boolean>>): ConfirmationPayload {
  return {
    callId: 'call-1',
    tool: 'create_audio_download',
    risk: 'confirmation_required',
    summary: 'Download audio',
    args: {
      chapter_from: 1,
      chapter_to: 1,
      provider: 'edge',
      voice: null,
      rate: 1,
    },
    form: {
      fields: [
        field('chapter_from', true),
        field('chapter_to', true),
        field('provider', provided.provider),
        field('voice', provided.voice),
        field('rate', provided.rate),
      ],
    },
    status: 'pending',
  }
}

function field(name: string, provided?: boolean) {
  return {
    name,
    label: name,
    type: name === 'rate' ? 'number' : 'string',
    required: name !== 'voice',
    default: null,
    provided,
  }
}

describe('audio confirmation defaults', () => {
  it('uses the same persisted TTS defaults as the download modal', () => {
    const values = defaultsFrom(
      audioPayload({ provider: false, voice: false, rate: false }),
      {
        provider: 'sapi',
        serverVoice: null,
        rate: 2,
      },
    )

    expect(values.provider).toBe('sapi')
    expect(values.voice).toBe('Microsoft Zira Desktop')
    expect(values.rate).toBe(1.35)
  })

  it('preserves audio options explicitly requested in chat', () => {
    const payload = audioPayload({ provider: true, voice: true, rate: true })
    payload.args = {
      ...payload.args,
      provider: 'edge',
      voice: 'en-US-AvaNeural',
      rate: 1.5,
    }

    const values = defaultsFrom(payload, {
      provider: 'sapi',
      serverVoice: null,
      rate: 2,
    })

    expect(values.provider).toBe('edge')
    expect(values.voice).toBe('en-US-AvaNeural')
    expect(values.rate).toBe(1.5)
  })
})
