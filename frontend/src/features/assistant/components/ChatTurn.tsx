import type { ChatMessage } from '../api/chatApi'
import { ChoiceChips } from './ChoiceChips'
import { ConfirmationCard } from './ConfirmationCard'
import { AssistantProse, CancelledNote, UserBubble } from './chatTurnParts'
import { ToolResultCard } from './ToolResultCard'

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
  return <AssistantProse content={message.content} streaming={streaming} />
}
