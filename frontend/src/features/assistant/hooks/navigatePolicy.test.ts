import { describe, expect, it } from 'vitest'
import { shouldAutoNavigate } from './navigatePolicy'

describe('shouldAutoNavigate', () => {
  it('auto-opens reader paths when off-chapter', () => {
    expect(
      shouldAutoNavigate(
        { type: 'navigate', path: '/read/b/c', label: 'Open chapter' },
        '/library',
      ),
    ).toBe(true)
  })

  it('skips when already on the chapter', () => {
    expect(
      shouldAutoNavigate(
        { type: 'navigate', path: '/read/b/c', label: 'Open chapter' },
        '/read/b/c',
      ),
    ).toBe(false)
  })

  it('does not auto-open scraper', () => {
    expect(
      shouldAutoNavigate(
        { type: 'navigate', path: '/scraper', label: 'Open Scraper' },
        '/library',
      ),
    ).toBe(false)
  })
})
