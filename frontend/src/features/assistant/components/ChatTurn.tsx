import type { ChatMessage } from '../api/chatApi'
import { ChoiceChips } from './ChoiceChips'
import { ConfirmationCard } from './ConfirmationCard'
import {
  AssistantProse,
  CancelledNote,
  QuotaRefusalNote,
  UserBubble,
} from './chatTurnParts'
import { ToolResultCard } from './ToolResultCard'

/** Roles rendered as assistant prose; anything else degrades to a muted note. */
const PROSE_ROLES = new Set<string>(['assistant', 'system', 'step'])

type Props = {
  message: ChatMessage
  streaming?: boolean
  confirmBusy?: boolean
  choicesDisabled?: boolean
  onResolveConfirm?: (approved: boolean, values?: Record<string, unknown>) => void
  onPickChoice?: (label: string) => void
}

/** One chat turn — user bubbled; assistant prose; HITL / tool / choice cards. */
export function ChatTurn({
  message,
  streaming = false,
  confirmBusy = false,
  choicesDisabled = false,
  onResolveConfirm,
  onPickChoice,
}: Props) {
  if (message.role === 'user') return <UserBubble content={message.content} />
  if (message.role === 'cancelled') return <CancelledNote content={message.content} />
  if (message.role === 'quota_refusal')
    return <QuotaRefusalNote content={message.content} />
  if (message.role === 'confirmation' && message.confirmation) {
    return (
      <ConfirmationCard
        payload={message.confirmation}
        busy={confirmBusy}
        onResolve={onResolveConfirm ?? (() => undefined)}
      />
    )
  }
  if (message.role === 'choice' && message.choice) {
    return (
      <ChoiceChips
        payload={message.choice}
        disabled={choicesDisabled}
        onPick={onPickChoice ?? (() => undefined)}
      />
    )
  }
  if (message.role === 'tool') {
    return (
      <ToolResultCard
        name={message.toolName ?? 'tool'}
        ok={message.toolOk !== false}
        summary={message.content}
        clientAction={message.clientAction}
      />
    )
  }
  // Future persisted roles must degrade visibly, not vanish.
  if (!PROSE_ROLES.has(message.role))
    return <QuotaRefusalNote content={message.content} />
  return <AssistantProse content={message.content} streaming={streaming} />
}
