import { describe, expect, it } from 'vitest'
import {
  chatUiLang,
  firstStrongLang,
  langFromMessages,
  textDirForLang,
} from './textDirection'

describe('textDirection', () => {
  it('detects Hebrew as first strong letter', () => {
    expect(firstStrongLang('איזה ספרים like Against the Gods?')).toBe('he')
    expect(chatUiLang('שלום')).toBe('he')
    expect(textDirForLang('he')).toBe('rtl')
  })

  it('detects Latin and skips neutrals', () => {
    expect(firstStrongLang('*** Hello')).toBe('en')
    expect(firstStrongLang('123 books')).toBe('en')
    expect(chatUiLang('Hello')).toBe('en')
    expect(textDirForLang('en')).toBe('ltr')
  })

  it('flags Arabic separately from Hebrew', () => {
    expect(firstStrongLang('مرحبا')).toBe('ar')
    expect(chatUiLang('مرحبا')).toBe('en')
  })

  it('uses nearest preceding user message for turn language', () => {
    const messages = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi' },
      { role: 'user', content: 'התחרטתי' },
      { role: 'confirmation', content: '' },
    ]
    expect(langFromMessages(messages, 1)).toBe('en')
    expect(langFromMessages(messages, 3)).toBe('he')
  })
})
