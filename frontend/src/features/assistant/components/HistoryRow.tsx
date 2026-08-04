import { motion } from 'motion/react'
import { Loader2, Trash2 } from 'lucide-react'
import type { ConversationSummary } from '../api/chatApi'
import { Button, IconTooltip } from '@/shared/ui'
import { truncateHistoryTitle } from '../logic/truncateHistoryTitle'

export function HistoryRow({
  item,
  active,
  disabled,
  deleting,
  index,
  onSelect,
  onDelete,
}: {
  item: ConversationSummary
  active: boolean
  disabled: boolean
  deleting: boolean
  index: number
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}) {
  const title = truncateHistoryTitle(item.title)
  const busy = disabled || deleting
  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index, 12) * 0.03, duration: 0.2 }}
      className={rowClass(active)}
    >
      <button
        type="button"
        disabled={busy}
        onClick={() => onSelect(item.id)}
        className="flex min-w-0 flex-1 flex-col gap-0.5 px-3 py-2.5 text-left disabled:opacity-60"
      >
        <span
          className="block truncate text-sm font-medium"
          title={item.title ?? undefined}
        >
          {title}
        </span>
        <span className="block text-[11px] text-muted-foreground">
          {new Date(item.updated_at).toLocaleString()}
        </span>
      </button>
      <DeleteHistoryButton
        busy={busy}
        deleting={deleting}
        onDelete={() => onDelete(item.id)}
      />
    </motion.li>
  )
}

function rowClass(active: boolean): string {
  return active
    ? 'group flex items-stretch gap-1 rounded-lg bg-muted'
    : 'group flex items-stretch gap-1 rounded-lg hover:bg-muted/70'
}

function DeleteHistoryButton({
  busy,
  deleting,
  onDelete,
}: {
  busy: boolean
  deleting: boolean
  onDelete: () => void
}) {
  return (
    <IconTooltip label="Delete chat">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled={busy}
        aria-label="Delete chat"
        className="m-1 h-8 w-8 shrink-0 self-center text-muted-foreground opacity-70 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 disabled:opacity-40"
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
      >
        {deleting ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Trash2 className="h-3.5 w-3.5" />
        )}
      </Button>
    </IconTooltip>
  )
}
