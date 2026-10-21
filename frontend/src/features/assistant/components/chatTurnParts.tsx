import { motion } from 'motion/react'
import { useMemo } from 'react'
import { Streamdown } from 'streamdown'
import type { LinkSafetyModalProps } from 'streamdown'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import { textDirForLang } from '@/shared/lib/textDirection'
import { ExternalLinkSafetyModal } from './ExternalLinkSafetyModal'
import 'streamdown/styles.css'

export function UserBubble({ content, uiLang }: { content: string; uiLang: ChatUiLang }) {
  return (
    <div className="flex justify-end">
      <div
        dir={textDirForLang(uiLang)}
        className="max-w-[85%] rounded-2xl bg-primary px-3.5 py-2 text-sm leading-relaxed whitespace-pre-wrap text-primary-foreground"
      >
        {content}
      </div>
    </div>
  )
}

export function CancelledNote({
  content,
  uiLang,
}: {
  content: string
  uiLang: ChatUiLang
}) {
  return (
    <p dir={textDirForLang(uiLang)} className="px-1 text-xs text-muted-foreground/70">
      {content}
    </p>
  )
}

export function QuotaRefusalNote({
  content,
  uiLang,
}: {
  content: string
  uiLang: ChatUiLang
}) {
  return (
    <p
      dir={textDirForLang(uiLang)}
      className="rounded-xl bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300"
    >
      {content}
    </p>
  )
}

export function AssistantProse({
  content,
  streaming,
  uiLang,
}: {
  content: string
  streaming: boolean
  uiLang: ChatUiLang
}) {
  const linkSafety = useMemo(
    () => ({
      enabled: true as const,
      renderModal: (props: LinkSafetyModalProps) => (
        <ExternalLinkSafetyModal {...props} uiLang={uiLang} />
      ),
    }),
    [uiLang],
  )
  return (
    <motion.div
      className="w-full"
      initial={false}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.12 }}
    >
      <div dir={textDirForLang(uiLang)} className="assistant-md text-sm text-foreground">
        {content ? (
          <Streamdown isAnimating={streaming} linkSafety={linkSafety}>
            {content}
          </Streamdown>
        ) : streaming ? (
          <span className="assistant-stream-caret" aria-hidden />
        ) : null}
      </div>
    </motion.div>
  )
}
