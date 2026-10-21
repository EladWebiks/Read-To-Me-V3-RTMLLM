import assistantEn from './locales/en/assistant.json'
import commonEn from './locales/en/common.json'
import assistantHe from './locales/he/assistant.json'

export const defaultNS = 'common' as const

export const resources = {
  en: {
    common: commonEn,
    assistant: assistantEn,
  },
  he: {
    common: commonEn,
    assistant: assistantHe,
  },
} as const
