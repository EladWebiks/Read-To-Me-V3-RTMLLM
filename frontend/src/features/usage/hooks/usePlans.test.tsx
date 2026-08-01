import type { ReactNode } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { meQueryKey } from '@/features/auth/hooks'
import { meUsageKey } from './useMeUsage'
import { plansKey, useSwitchPlan } from './usePlans'
import { switchPlan } from '../api/plans'

vi.mock('../api/plans', () => ({
  fetchPlans: vi.fn(),
  switchPlan: vi.fn(),
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

describe('useSwitchPlan', () => {
  it('calls the API and invalidates plans, usage, and the auth me query', async () => {
    vi.mocked(switchPlan).mockResolvedValue({} as never)
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderWithClient(() => useSwitchPlan(), queryClient)

    act(() => {
      result.current.mutate('premium')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(switchPlan).toHaveBeenCalledWith('premium')
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: plansKey })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: meUsageKey })
    // Regression: without this, the navbar avatar keeps showing the
    // pre-switch plan until the 60s `me` staleTime lapses.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: meQueryKey })
  })
})
