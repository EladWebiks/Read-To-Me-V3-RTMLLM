import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import '@/shared/i18n'
import type { ConfirmationPayload } from '../api/chatApi'
import { ConfirmationCard } from './ConfirmationCard'

vi.mock('@/features/reader/hooks/ttsSettingsStore', () => ({
  useTtsSettings: () => ({
    provider: 'sapi',
    serverVoice: 'Zira',
    rate: 1.35,
  }),
}))

afterEach(() => {
  cleanup()
})

function payload(overrides: Partial<ConfirmationPayload> = {}): ConfirmationPayload {
  return {
    callId: 'c1',
    tool: 'import_discovered_book',
    risk: 'confirmation_required',
    summary: 'Import book: Starfall',
    action: 'Import book',
    title: 'Starfall',
    subtitle: 'novelbin',
    args: {},
    form: {
      fields: [
        {
          name: 'start_chapter',
          label: 'Starting chapter',
          type: 'integer',
          required: false,
          default: 1,
        },
      ],
    },
    status: 'pending',
    ...overrides,
  }
}

describe('ConfirmationCard', () => {
  it('shows action and book title', () => {
    render(
      <ConfirmationCard
        payload={payload()}
        uiLang="en"
        busy={false}
        onResolve={vi.fn()}
      />,
    )
    expect(screen.getByText('Import book')).toBeTruthy()
    expect(screen.getByText('Starfall')).toBeTruthy()
    expect(screen.queryByText('novelbin')).toBeNull()
    expect(screen.queryByText(/Confirm/)).toBeNull()
  })

  it('shows source subtitle when there is no chapter range form', () => {
    render(
      <ConfirmationCard
        payload={payload({ form: { fields: [] }, subtitle: 'novelbin' })}
        uiLang="en"
        busy={false}
        onResolve={vi.fn()}
      />,
    )
    expect(screen.getByText('novelbin')).toBeTruthy()
  })

  it('calls onResolve(true) when Approve is clicked', () => {
    const onResolve = vi.fn()
    render(
      <ConfirmationCard
        payload={payload()}
        uiLang="en"
        busy={false}
        onResolve={onResolve}
      />,
    )
    fireEvent.click(screen.getAllByRole('button', { name: 'Approve' })[0]!)
    expect(onResolve).toHaveBeenCalledWith(true, expect.any(Object))
  })
})
