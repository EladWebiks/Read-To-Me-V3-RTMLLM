import { motion } from 'motion/react'
import { Loader2, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation('assistant')
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
        className="flex min-w-0 flex-1 flex-col gap-0.5 px-3 py-2.5 text-start disabled:opacity-60"
      >
        <span
          dir="auto"
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
        label={t('history.delete')}
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
  label,
  onDelete,
}: {
  busy: boolean
  deleting: boolean
  label: string
  onDelete: () => void
}) {
  return (
    <IconTooltip label={label}>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled={busy}
        aria-label={label}
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
