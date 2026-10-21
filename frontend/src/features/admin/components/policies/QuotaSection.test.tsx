import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QuotaSection } from './QuotaSection'
import {
  deleteMembershipQuota,
  putMembershipQuota,
} from '@/features/admin/api/membershipQuotas'
import { ApiError } from '@/shared/lib/api'

vi.mock('@/features/admin/api/membershipQuotas', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  putMembershipQuota: vi.fn(),
  deleteMembershipQuota: vi.fn(),
}))

const KINDS = [
  { kind: 'llm_tokens', label: 'AI tokens', unit: 'tokens', window: 'month' as const },
  {
    kind: 'storage_bytes',
    label: 'Download storage',
    unit: 'bytes',
    window: 'standing' as const,
  },
]

const ROWS = [
  {
    membership: 'free',
    quota_kind: 'llm_tokens',
    limit_value: 500000,
    updated_at: '2026-07-31T00:00:00Z',
  },
]

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <QuotaSection membership="free" kinds={KINDS} rows={ROWS} />
    </QueryClientProvider>,
  )
}

// vitest runs with globals:false, so testing-library's auto-cleanup is not registered.
afterEach(cleanup)
// ...and no clearMocks config either, so call history would leak between tests.
beforeEach(() => vi.clearAllMocks())

describe('QuotaSection', () => {
  it('renders unlimited placeholder for kinds without a rule', () => {
    renderSection()
    expect(screen.getByDisplayValue('500000')).toBeTruthy()
    expect(screen.getAllByPlaceholderText('unlimited').length).toBe(1)
  })

  it('spells out that blank and 0 are different', () => {
    renderSection()
    expect(screen.getByText(/Blank = unlimited/)).toBeTruthy()
  })

  it('PUTs 0 as a blocking limit rather than clearing the rule', async () => {
    vi.mocked(putMembershipQuota).mockResolvedValue({ ...ROWS[0], limit_value: 0 })
    renderSection()
    fireEvent.change(screen.getByDisplayValue('500000'), { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save quotas' }))
    await waitFor(() => {
      expect(vi.mocked(putMembershipQuota)).toHaveBeenCalledWith('free', 'llm_tokens', 0)
    })
    expect(vi.mocked(deleteMembershipQuota)).not.toHaveBeenCalled()
  })

  it('PUTs changed values and DELETEs blanked ones on save', async () => {
    vi.mocked(putMembershipQuota).mockResolvedValue(ROWS[0])
    vi.mocked(deleteMembershipQuota).mockResolvedValue(undefined)
    renderSection()
    fireEvent.change(screen.getByPlaceholderText('unlimited'), {
      target: { value: '1000000' },
    })
    fireEvent.change(screen.getByDisplayValue('500000'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save quotas' }))
    await waitFor(() => {
      expect(vi.mocked(putMembershipQuota)).toHaveBeenCalledWith(
        'free',
        'storage_bytes',
        1000000,
      )
      expect(vi.mocked(deleteMembershipQuota)).toHaveBeenCalledWith('free', 'llm_tokens')
    })
  })
})

describe('QuotaSection rainy days', () => {
  it('shows why the API rejected the write instead of failing silently', async () => {
    vi.mocked(putMembershipQuota).mockRejectedValue(
      new ApiError(422, 'limit_value: Input should be greater than or equal to 0'),
    )
    renderSection()
    fireEvent.change(screen.getByDisplayValue('500000'), { target: { value: '7' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save quotas' }))
    expect(
      await screen.findByText('limit_value: Input should be greater than or equal to 0'),
    ).toBeTruthy()
  })

  it('shows why a clearing DELETE failed', async () => {
    vi.mocked(deleteMembershipQuota).mockRejectedValue(
      new ApiError(404, 'No quota rule for free/llm_tokens'),
    )
    renderSection()
    fireEvent.change(screen.getByDisplayValue('500000'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save quotas' }))
    expect(await screen.findByText('No quota rule for free/llm_tokens')).toBeTruthy()
  })

  it('refuses to send a value the API would reject, and says why', async () => {
    renderSection()
    fireEvent.change(screen.getByDisplayValue('500000'), { target: { value: '-1' } })
    expect(screen.getByText(/Enter a number/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Save quotas' }))
    await waitFor(() => expect(vi.mocked(putMembershipQuota)).not.toHaveBeenCalled())
  })

  it('flags a non-numeric entry rather than dropping the whole save', async () => {
    renderSection()
    fireEvent.change(screen.getByPlaceholderText('unlimited'), {
      target: { value: '5000' },
    })
    fireEvent.change(screen.getByDisplayValue('500000'), { target: { value: 'abc' } })
    expect(screen.getByText(/Enter a number/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Save quotas' }))
    // the valid sibling must not be silently skipped either — the admin gets told, not ignored
    await waitFor(() => expect(vi.mocked(putMembershipQuota)).not.toHaveBeenCalled())
  })
})
