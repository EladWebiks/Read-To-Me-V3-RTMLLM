import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AssistantComposer } from './AssistantComposer'

const NOTICE = 'Monthly AI limit reached — resets August 1, 2026'

function renderComposer(quotaNotice: string | null) {
  return render(
    <AssistantComposer
      draft=""
      setDraft={vi.fn()}
      sending={false}
      status={null}
      blocked={false}
      quotaNotice={quotaNotice}
      onSend={vi.fn()}
      onCancel={vi.fn()}
    />,
  )
}

describe('AssistantComposer quota lock', () => {
  afterEach(cleanup)

  it('disables input and shows the notice when quotaNotice is set', () => {
    renderComposer(NOTICE)
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
    expect(textarea.disabled).toBe(true)
    expect(textarea.getAttribute('placeholder')).toBe(NOTICE)
    expect(screen.getByText(NOTICE)).toBeTruthy()
  })

  it('stays enabled without a quotaNotice', () => {
    renderComposer(null)
    expect((screen.getByRole('textbox') as HTMLTextAreaElement).disabled).toBe(false)
  })
})
