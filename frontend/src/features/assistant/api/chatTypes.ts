/** Shared chat / SSE types for the assistant. */

import type { ClientAction } from './clientActionTypes'

export type {
  ClientAction,
  DownloadClientAction,
  UiSettingsPatch,
} from './clientActionTypes'

export type ChatRole =
  | 'user'
  | 'assistant'
  | 'system'
  | 'step'
  | 'tool'
  | 'confirmation'
  | 'choice'
  | 'cancelled'

export type ConfirmationFormField = {
  name: string
  label: string
  type: string
  required: boolean
  default: unknown
  provided?: boolean
  min?: number
  max?: number
  options?: Array<{ value: string; label: string }>
}

export type ConfirmationPayload = {
  callId: string
  tool: string
  risk: string
  summary: string
  args: Record<string, unknown>
  form: { fields: ConfirmationFormField[] } | null
  status: 'pending' | 'approved' | 'rejected'
}

export type ChoiceOption = {
  id: string
  label: string
}

export type ChoicePayload = {
  prompt: string
  options: ChoiceOption[]
}

export type ChatMessage = {
  id: string
  role: ChatRole
  content: string
  created_at?: string
  toolName?: string
  toolOk?: boolean
  clientAction?: ClientAction
  confirmation?: ConfirmationPayload
  choice?: ChoicePayload
}

export type Conversation = {
  id: string
  title: string | null
  messages: ChatMessage[]
}

export type DonePayload = {
  messageId: string
  conversationId: string
  status?: string
  callId?: string
}

export type ChatStreamHandlers = {
  onMeta: (conversationId: string) => void
  onDelta: (text: string) => void
  onStep?: (label: string) => void
  onToolResult?: (payload: {
    name: string
    ok: boolean
    summary: string
    clientAction?: ClientAction
  }) => void
  onConfirmation?: (payload: ConfirmationPayload) => void
  onChoiceRequest?: (payload: ChoicePayload) => void
  onDone: (payload: DonePayload) => void
  onError: (detail: string) => void
}
