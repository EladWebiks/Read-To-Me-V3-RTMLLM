import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import '@/shared/i18n'
import type { ConfirmationPayload } from '../api/chatApi'
import { AssistantComposer } from './AssistantComposer'
import { AssistantProse, UserBubble } from './chatTurnParts'
import { ConfirmationPending } from './ConfirmationPending'

afterEach(cleanup)

describe('chat direction', () => {
  it('keeps empty composer English/LTR with send on the right', () => {
    const { container } = render(
      <AssistantComposer
        draft=""
        setDraft={() => undefined}
        sending={false}
        onSend={() => undefined}
      />,
    )
    const form = container.querySelector('form')
    const textarea = screen.getByLabelText('Message')
    expect(form?.getAttribute('dir')).toBe('ltr')
    expect(textarea.getAttribute('dir')).toBe('ltr')
    expect(textarea.getAttribute('placeholder')).toBe('Ask anything…')
  })

  it('RTL only the textarea while typing Hebrew; form stays LTR', () => {
    const { container } = render(
      <AssistantComposer
        draft="שלום"
        setDraft={() => undefined}
        sending={false}
        onSend={() => undefined}
      />,
    )
    expect(container.querySelector('form')?.getAttribute('dir')).toBe('ltr')
    expect(screen.getByLabelText('Message').getAttribute('dir')).toBe('rtl')
  })

  it('marks user and assistant prose from uiLang', () => {
    const { container: user } = render(<UserBubble content="שלום" uiLang="he" />)
    expect(user.querySelector('[dir="rtl"]')).toBeTruthy()
    const { container: prose } = render(
      <AssistantProse content="Hello" streaming={false} uiLang="he" />,
    )
    expect(prose.querySelector('.assistant-md')?.getAttribute('dir')).toBe('rtl')
  })

  it('localizes HITL chrome to Hebrew', () => {
    const payload: ConfirmationPayload = {
      callId: 'c1',
      tool: 'import_discovered_book',
      risk: 'confirmation_required',
      summary: 'Import',
      action: 'Import book',
      title: 'I Shall Seal the Heavens',
      subtitle: null,
      args: {},
      form: null,
      status: 'pending',
    }
    render(
      <ConfirmationPending
        payload={payload}
        uiLang="he"
        busy={false}
        error={null}
        onApprove={() => undefined}
        onCancel={() => undefined}
      />,
    )
    expect(screen.getByText('ייבוא ספר')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'אישור' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'ביטול' })).toBeTruthy()
  })
})
