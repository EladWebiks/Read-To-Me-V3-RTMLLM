import type { ReactNode } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  membershipsKey,
  useCreateMembership,
  useDeactivateMembership,
  usePatchMembership,
} from './useMemberships'
import { membershipPoliciesKey } from './useMembershipPolicies'
import { usersKey as adminUsersKey } from './useAdminUsers'
import {
  createMembership,
  deactivateMembership,
  patchMembership,
} from '@/features/admin/api/memberships'

vi.mock('@/features/admin/api/memberships', () => ({
  fetchMemberships: vi.fn(),
  createMembership: vi.fn(),
  patchMembership: vi.fn(),
  deactivateMembership: vi.fn(),
}))

function renderWithClient<T>(hook: () => T, queryClient: QueryClient) {
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return renderHook(hook, { wrapper })
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('useMemberships mutations', () => {
  it('useCreateMembership calls the API and invalidates all three keys', async () => {
    vi.mocked(createMembership).mockResolvedValue({} as never)
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderWithClient(() => useCreateMembership(), queryClient)

    act(() => {
      result.current.mutate({ slug: 'gold', label: 'Gold', rank: 3 })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(createMembership).toHaveBeenCalledWith({
      slug: 'gold',
      label: 'Gold',
      rank: 3,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: membershipsKey })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: membershipPoliciesKey })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: adminUsersKey })
  })

  it('usePatchMembership calls the API and invalidates all three keys', async () => {
    vi.mocked(patchMembership).mockResolvedValue({} as never)
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderWithClient(() => usePatchMembership(), queryClient)

    act(() => {
      result.current.mutate({ slug: 'free', patch: { label: 'Free tier' } })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(patchMembership).toHaveBeenCalledWith('free', { label: 'Free tier' })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: membershipsKey })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: membershipPoliciesKey })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: adminUsersKey })
  })

  it('useDeactivateMembership calls the API and invalidates all three keys', async () => {
    vi.mocked(deactivateMembership).mockResolvedValue({} as never)
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderWithClient(() => useDeactivateMembership(), queryClient)

    act(() => {
      result.current.mutate({ slug: 'legacy', migrateTo: 'free' })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(deactivateMembership).toHaveBeenCalledWith('legacy', 'free')
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: membershipsKey })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: membershipPoliciesKey })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: adminUsersKey })
  })
})
