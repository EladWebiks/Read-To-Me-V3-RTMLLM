/** First-strong script / direction from Unicode letter classes (not dir=auto alone). */

export type TextDir = 'ltr' | 'rtl'
export type ChatUiLang = 'en' | 'he'

const HEBREW = /\p{Script=Hebrew}/u
const ARABIC = /\p{Script=Arabic}/u
const LATIN = /\p{Script=Latin}/u

/** Skip marks/numbers/punctuation; return first strong letter's script. */
export function firstStrongLang(text: string): ChatUiLang | 'ar' | null {
  for (const char of text) {
    if (HEBREW.test(char)) return 'he'
    if (ARABIC.test(char)) return 'ar'
    if (LATIN.test(char)) return 'en'
  }
  return null
}

/** UI language for chat chrome: Hebrew only when first strong letter is Hebrew. */
export function chatUiLang(text: string | null | undefined): ChatUiLang {
  const strong = firstStrongLang(text ?? '')
  return strong === 'he' ? 'he' : 'en'
}

export function textDirForLang(lang: ChatUiLang): TextDir {
  return lang === 'he' ? 'rtl' : 'ltr'
}

/** Prefer the nearest preceding user message; fall back to the message itself. */
export function langFromMessages(
  messages: ReadonlyArray<{ role: string; content: string }>,
  index: number,
): ChatUiLang {
  for (let i = index; i >= 0; i -= 1) {
    const row = messages[i]
    if (row?.role === 'user' && row.content.trim()) {
      return chatUiLang(row.content)
    }
  }
  return 'en'
}

export function lastUserLang(
  messages: ReadonlyArray<{ role: string; content: string }>,
): ChatUiLang {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const row = messages[i]
    if (row?.role === 'user' && row.content.trim()) {
      return chatUiLang(row.content)
    }
  }
  return 'en'
}
