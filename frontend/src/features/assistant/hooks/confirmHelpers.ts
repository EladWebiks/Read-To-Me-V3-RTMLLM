import type { Dispatch, SetStateAction } from 'react'
import type { ChatMessage } from '../api/chatApi'

export function markConfirmStatus(
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  callId: string,
  status: 'approved' | 'rejected',
): void {
  setMessages((prev) =>
    prev.map((m) =>
      m.confirmation?.callId === callId && m.confirmation
        ? { ...m, confirmation: { ...m.confirmation, status } }
        : m,
    ),
  )
}
