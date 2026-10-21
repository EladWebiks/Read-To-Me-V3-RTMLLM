import { useContext } from 'react'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import { ChatUiLangContext } from './chatUiLangContext'

export function useChatUiLang(): ChatUiLang {
  return useContext(ChatUiLangContext)
}
