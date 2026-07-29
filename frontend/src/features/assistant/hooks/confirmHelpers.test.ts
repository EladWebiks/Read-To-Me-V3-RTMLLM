import { describe, expect, it } from 'vitest'
import type { SetStateAction } from 'react'
import type { ChatMessage } from '../api/chatApi'
import { markConfirmStatus } from './confirmHelpers'

function confirmationMessage(): ChatMessage {
  return {
    id: 'confirm-1',
    role: 'confirmation',
    content: 'Create audio',
    confirmation: {
      callId: 'call-1',
      tool: 'create_audio_download',
      risk: 'confirmation_required',
      summary: 'Create audio',
      args: {},
      form: null,
      status: 'pending',
    },
  }
}

describe('markConfirmStatus', () => {
  it('removes an approved confirmation instead of rendering an approval bubble', () => {
    let messages = [confirmationMessage()]
    const setMessages = (update: SetStateAction<ChatMessage[]>) => {
      messages = typeof update === 'function' ? update(messages) : update
    }

    markConfirmStatus(setMessages, 'call-1', 'approved')

    expect(messages).toEqual([])
  })
})
