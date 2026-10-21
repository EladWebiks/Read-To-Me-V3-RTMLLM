import { createContext } from 'react'
import type { ChatUiLang } from '@/shared/lib/textDirection'

export const ChatUiLangContext = createContext<ChatUiLang>('en')
