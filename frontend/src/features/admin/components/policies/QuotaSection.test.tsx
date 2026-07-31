import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { QuotaSection } from './QuotaSection'
import {
  deleteMembershipQuota,
  putMembershipQuota,
} from '@/features/admin/api/membershipQuotas'

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

describe('QuotaSection', () => {
  it('renders unlimited placeholder for kinds without a rule', () => {
    renderSection()
    expect(screen.getByDisplayValue('500000')).toBeTruthy()
    expect(screen.getAllByPlaceholderText('unlimited').length).toBe(1)
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
