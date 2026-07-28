import { describe, expect, it } from 'vitest'
import type { ChatMessage } from '../api/chatApi'
import { isVisibleToolMessage } from './toolVisibility'

function tool(partial: Partial<ChatMessage>): ChatMessage {
  return {
    id: 't1',
    role: 'tool',
    content: 'summary',
    toolName: 'get_book_details',
    toolOk: true,
    ...partial,
  }
}

describe('isVisibleToolMessage', () => {
  it('hides successful read tools without navigate', () => {
    expect(isVisibleToolMessage(tool({}))).toBe(false)
  })

  it('shows failures', () => {
    expect(isVisibleToolMessage(tool({ toolOk: false }))).toBe(true)
  })

  it('shows navigate affordances', () => {
    expect(
      isVisibleToolMessage(
        tool({
          toolName: 'scrape_book_range',
          clientAction: { type: 'navigate', path: '/scraper', label: 'Open Scraper' },
        }),
      ),
    ).toBe(true)
  })

  it('hides propose_choices', () => {
    expect(isVisibleToolMessage(tool({ toolName: 'propose_choices' }))).toBe(false)
  })
})
