import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { deleteConversation, listConversations } from '../api/chatApi'
import { useAssistantStore } from '../assistantStore'
import { Button } from '@/shared/ui'
import { ChatHistoryDrawerBody } from './ChatHistoryDrawerBody'

const CONVERSATIONS_KEY = ['chat', 'conversations'] as const

export function ChatHistoryDrawer({
  open,
  activeId,
  selecting,
  onClose,
  onSelect,
}: {
  open: boolean
  activeId: string | null
  selecting: boolean
  onClose: () => void
  onSelect: (id: string) => void
}) {
  const { t } = useTranslation('assistant')
  const queryClient = useQueryClient()
  const requestNewChat = useAssistantStore((s) => s.requestNewChat)
  const query = useQuery({
    queryKey: CONVERSATIONS_KEY,
    queryFn: () => listConversations(50, 0),
    enabled: open,
  })
  const remove = useMutation({
    mutationFn: deleteConversation,
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY })
      if (id === activeId) requestNewChat()
    },
  })

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="history-drawer"
          className="absolute inset-0 z-20 flex flex-col bg-card/95 backdrop-blur-md"
          initial={{ opacity: 0, x: 28 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 20 }}
          transition={{ type: 'spring', stiffness: 380, damping: 34 }}
          role="dialog"
          aria-modal="true"
          aria-label={t('history.title')}
        >
          <DrawerHeader onClose={onClose} />
          <ChatHistoryDrawerBody
            loading={query.isLoading}
            error={query.isError || (!query.isLoading && !query.data)}
            items={query.data?.items ?? []}
            activeId={activeId}
            selecting={selecting}
            deletingId={remove.isPending ? (remove.variables ?? null) : null}
            onSelect={onSelect}
            onDelete={(id) => remove.mutate(id)}
            onRetry={() => void query.refetch()}
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}

function DrawerHeader({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation('assistant')
  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border/80 px-4 py-3">
      <div>
        <h3 className="text-sm font-semibold">{t('history.button')}</h3>
        <p className="text-xs text-muted-foreground">{t('history.subtitle')}</p>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        aria-label={t('history.close')}
        onClick={onClose}
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  )
}
