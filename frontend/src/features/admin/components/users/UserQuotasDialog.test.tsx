import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { UserQuotasDialog } from './UserQuotasDialog'
import {
  deleteUserQuota,
  fetchUserQuotas,
  putUserQuota,
} from '@/features/admin/api/userQuotas'
import { ApiError } from '@/shared/lib/api'

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
// ...and no clearMocks config either, so call history would leak between tests.
beforeEach(() => vi.clearAllMocks())

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

  it('saves 0 as a real override — it is no allowance, not unlimited', async () => {
    vi.mocked(fetchUserQuotas).mockResolvedValue(QUOTAS)
    vi.mocked(putUserQuota).mockResolvedValue({
      quota_kind: 'llm_tokens',
      limit_value: 0,
      updated_at: '',
    })
    renderDialog()

    const tokens = await screen.findByPlaceholderText('1,000 (tier)')
    fireEvent.change(tokens, { target: { value: '0' } })
    fireEvent.blur(tokens)
    await waitFor(() => {
      expect(vi.mocked(putUserQuota)).toHaveBeenCalledWith('u1', 'llm_tokens', 0)
    })
    expect(vi.mocked(deleteUserQuota)).not.toHaveBeenCalled()
  })
})

describe('UserQuotasDialog rainy days', () => {
  it('shows why the API rejected the override', async () => {
    vi.mocked(fetchUserQuotas).mockResolvedValue(QUOTAS)
    vi.mocked(putUserQuota).mockRejectedValue(
      new ApiError(422, 'limit_value: Input should be greater than or equal to 0'),
    )
    renderDialog()

    const tokens = await screen.findByPlaceholderText('1,000 (tier)')
    fireEvent.change(tokens, { target: { value: '9000' } })
    fireEvent.blur(tokens)
    expect(
      await screen.findByText('limit_value: Input should be greater than or equal to 0'),
    ).toBeTruthy()
  })

  it('explains a negative entry instead of dropping it', async () => {
    vi.mocked(fetchUserQuotas).mockResolvedValue(QUOTAS)
    renderDialog()

    const tokens = await screen.findByPlaceholderText('1,000 (tier)')
    fireEvent.change(tokens, { target: { value: '-5' } })
    fireEvent.blur(tokens)
    expect(await screen.findByText(/Enter a number/)).toBeTruthy()
    expect(vi.mocked(putUserQuota)).not.toHaveBeenCalled()
  })

  it('explains a non-numeric entry instead of dropping it', async () => {
    vi.mocked(fetchUserQuotas).mockResolvedValue(QUOTAS)
    renderDialog()

    const tokens = await screen.findByPlaceholderText('1,000 (tier)')
    fireEvent.change(tokens, { target: { value: 'lots' } })
    fireEvent.blur(tokens)
    expect(await screen.findByText(/Enter a number/)).toBeTruthy()
    expect(vi.mocked(putUserQuota)).not.toHaveBeenCalled()
  })
})
