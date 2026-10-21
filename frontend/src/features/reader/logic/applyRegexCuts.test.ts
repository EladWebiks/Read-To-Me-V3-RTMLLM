import { describe, expect, it } from 'vitest'
import { applyRegexCuts } from './applyRegexCuts'

describe('applyRegexCuts', () => {
  it('cuts translator header block before < Chapter marker', () => {
    const content = [
      "Absolute Regression - Chapter 389 : Where is the Young Cult Leader' Demonic Path - Novel Fire",
      '',
      'idle',
      '',
      'Translator: FenrirTL',
      '',
      'Editor/Quality Checker/Notes : Saphartlantis',
      '',
      '========================',
      '',
      "< Chapter 389: Where is the Young Cult Leader's Demonic Path >",
      '',
      'It was the moment...',
    ].join('\n')

    const pattern =
      'Absolute Regression\\s*-\\s*Chapter\\s*\\d+[\\s\\S]*?(?=<\\s*Chapter\\s*\\d+)'

    const { cleaned } = applyRegexCuts(content, [pattern])
    expect(cleaned).not.toContain('Translator:')
    expect(cleaned).toContain('< Chapter 389:')
    expect(cleaned).toContain('It was the moment...')
  })

  it('skips invalid regex patterns', () => {
    const content = 'hello world'
    const { cleaned } = applyRegexCuts(content, ['[bad-regex'])
    expect(cleaned).toBe(content)
  })
})
