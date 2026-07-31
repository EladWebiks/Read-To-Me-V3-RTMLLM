import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { UserQuotasDialog } from './UserQuotasDialog'
import {
  deleteUserQuota,
  fetchUserQuotas,
  putUserQuota,
} from '@/features/admin/api/userQuotas'

vi.mock('@/features/admin/api/userQuotas', () => ({
  fetchUserQuotas: vi.fn(),
  putUserQuota: vi.fn(),
  deleteUserQuota: vi.fn(),
}))

const QUOTAS = {
  membership: 'free',
  kinds: [
    { kind: 'llm_tokens', label: 'AI tokens', unit: 'tokens', window: 'month' as const },
    {
      kind: 'audio_chapters',
      label: 'Audio chapters',
      unit: 'chapters',
      window: 'month' as const,
    },
  ],
  tier_limits: { llm_tokens: 1000 },
  overrides: [{ quota_kind: 'audio_chapters', limit_value: 5, updated_at: '' }],
}

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UserQuotasDialog userId="u1" username="reader" open onOpenChange={() => {}} />
    </QueryClientProvider>,
  )
}

// vitest runs with globals:false, so testing-library's auto-cleanup is not registered.
afterEach(cleanup)

describe('UserQuotasDialog', () => {
  it('renders registry kinds with tier placeholders and override values', async () => {
    vi.mocked(fetchUserQuotas).mockResolvedValue(QUOTAS)
    renderDialog()
    expect(await screen.findByPlaceholderText('1,000 (tier)')).toBeTruthy()
    expect(screen.getByPlaceholderText('Unlimited (tier)')).toBeTruthy()
    expect(screen.getByDisplayValue('5')).toBeTruthy()
  })

  it('saves a number as PUT and blank as DELETE on blur', async () => {
    vi.mocked(fetchUserQuotas).mockResolvedValue(QUOTAS)
    vi.mocked(putUserQuota).mockResolvedValue({
      quota_kind: 'llm_tokens',
      limit_value: 9000,
      updated_at: '',
    })
    vi.mocked(deleteUserQuota).mockResolvedValue(undefined)
    renderDialog()

    const tokens = await screen.findByPlaceholderText('1,000 (tier)')
    fireEvent.change(tokens, { target: { value: '9000' } })
    fireEvent.blur(tokens)
    await waitFor(() => {
      expect(vi.mocked(putUserQuota)).toHaveBeenCalledWith('u1', 'llm_tokens', 9000)
    })

    const audio = screen.getByDisplayValue('5')
    fireEvent.change(audio, { target: { value: '' } })
    fireEvent.blur(audio)
    await waitFor(() => {
      expect(vi.mocked(deleteUserQuota)).toHaveBeenCalledWith('u1', 'audio_chapters')
    })
  })
})
