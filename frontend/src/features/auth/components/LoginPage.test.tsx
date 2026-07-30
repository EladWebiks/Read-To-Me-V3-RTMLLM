import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { GoogleLoginState } from '../hooks/useGoogleLogin'

const mocks = vi.hoisted(() => ({
  state: { status: 'idle' } as GoogleLoginState,
}))

vi.mock('@/features/auth/hooks', () => ({
  useGoogleLogin: () => ({ state: mocks.state, start: vi.fn() }),
}))

const { LoginPage } = await import('./LoginPage')

describe('LoginPage', () => {
  afterEach(() => {
    cleanup()
    mocks.state = { status: 'idle' }
  })

  it('renders no error message when idle', () => {
    const { container } = render(<LoginPage />)
    expect(container.querySelector('[aria-live="polite"]')?.textContent).toBe('')
  })

  it('announces the mapped message for a known reason', () => {
    mocks.state = { status: 'error', reason: 'google_identity_conflict' }
    const { container } = render(<LoginPage />)
    const live = container.querySelector('[aria-live="polite"]')
    expect(live?.textContent).toBe(
      'This account is already linked to a different Google account.',
    )
  })

  it('falls back for a prototype-chain reason instead of throwing', () => {
    // ERROR_MESSAGES['__proto__'] resolves to Object.prototype — truthy, not a
    // string, and fatal to React if it ever reached the render output.
    mocks.state = { status: 'error', reason: '__proto__' }
    const { container } = render(<LoginPage />)
    expect(container.querySelector('[aria-live="polite"]')?.textContent).toBe(
      'Google sign-in failed. Please try again.',
    )
  })
})
