import { motion } from 'motion/react'
import { Streamdown } from 'streamdown'
import type { ChatMessage } from '../api/chatApi'
import 'streamdown/styles.css'

type Props = {
  message: ChatMessage
  streaming?: boolean
}

/** One chat turn — user bubbled; assistant is natural prose + MD. */
export function ChatTurn({ message, streaming = false }: Props) {
  if (message.role === 'user') {
    return <UserBubble content={message.content} />
  }
  return <AssistantProse content={message.content} streaming={streaming} />
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl bg-primary px-3.5 py-2 text-sm leading-relaxed whitespace-pre-wrap text-primary-foreground">
        {content}
      </div>
    </div>
  )
}

function AssistantProse({ content, streaming }: { content: string; streaming: boolean }) {
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
        ) : (
          <span className="text-muted-foreground">…</span>
        )}
      </div>
    </motion.div>
  )
}
