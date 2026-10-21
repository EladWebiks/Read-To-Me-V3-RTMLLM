import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import '@/shared/i18n'
import { AssistantComposer } from './AssistantComposer'

describe('AssistantComposer autofocus', () => {
  afterEach(cleanup)

  it('refocuses the textarea when sending finishes', () => {
    const props = {
      draft: '',
      setDraft: () => undefined,
      status: null,
      blocked: false,
      quotaNotice: null,
      onSend: () => undefined,
      onCancel: () => undefined,
    }
    const { rerender } = render(<AssistantComposer {...props} sending />)
    const textarea = screen.getByRole('textbox')
    expect(document.activeElement).not.toBe(textarea)
    rerender(<AssistantComposer {...props} sending={false} />)
    expect(document.activeElement).toBe(textarea)
  })
})
