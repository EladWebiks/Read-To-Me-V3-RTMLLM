import { motion } from 'motion/react'
import { Streamdown } from 'streamdown'
import 'streamdown/styles.css'

export function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl bg-primary px-3.5 py-2 text-sm leading-relaxed whitespace-pre-wrap text-primary-foreground">
        {content}
      </div>
    </div>
  )
}

export function CancelledNote({ content }: { content: string }) {
  return <p className="px-1 text-xs text-muted-foreground/70">{content}</p>
}

export function QuotaRefusalNote({ content }: { content: string }) {
  return (
    <p className="rounded-xl bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
      {content}
    </p>
  )
}

export function AssistantProse({
  content,
  streaming,
}: {
  content: string
  streaming: boolean
}) {
  return (
    <motion.div
      className="w-full"
      initial={false}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.12 }}
    >
      <div className="assistant-md text-sm text-foreground">
        {content ? (
          <Streamdown isAnimating={streaming}>{content}</Streamdown>
        ) : streaming ? (
          <span className="assistant-stream-caret" aria-hidden />
        ) : null}
      </div>
    </motion.div>
  )
}
