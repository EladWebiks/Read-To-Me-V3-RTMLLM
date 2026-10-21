import type { ReactNode } from 'react'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import { ChatUiLangContext } from './chatUiLangContext'

export function ChatUiLangProvider({
  lang,
  children,
}: {
  lang: ChatUiLang
  children: ReactNode
}) {
  return <ChatUiLangContext.Provider value={lang}>{children}</ChatUiLangContext.Provider>
}
