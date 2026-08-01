import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryState } from './query-state'

afterEach(cleanup)

const base = {
  isPending: false,
  loading: <div data-testid="loader" />,
  errorLabel: "Couldn't load things.",
}

describe('QueryState', () => {
  it('renders children when not pending and not errored', () => {
    render(<QueryState {...base}>content</QueryState>)
    expect(screen.getByText('content')).toBeTruthy()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('renders error with role=alert, the label, and a Retry that calls onRetry', () => {
    const onRetry = vi.fn()
    render(
      <QueryState {...base} isError onRetry={onRetry}>
        content
      </QueryState>,
    )
    expect(screen.getByRole('alert').textContent).toContain("Couldn't load things.")
    expect(screen.queryByText('content')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders no Retry button when onRetry is omitted', () => {
    render(
      <QueryState {...base} isError>
        content
      </QueryState>,
    )
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('error takes precedence over pending', () => {
    render(
      <QueryState {...base} isPending isError>
        content
      </QueryState>,
    )
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('isEmpty renders emptyLabel, and children win when not empty', () => {
    const { rerender } = render(
      <QueryState {...base} isEmpty emptyLabel={<p>Nothing yet.</p>}>
        content
      </QueryState>,
    )
    expect(screen.getByText('Nothing yet.')).toBeTruthy()
    expect(screen.queryByText('content')).toBeNull()
    rerender(
      <QueryState {...base} emptyLabel={<p>Nothing yet.</p>}>
        content
      </QueryState>,
    )
    expect(screen.getByText('content')).toBeTruthy()
  })

  describe('delay window (fake timers)', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })
    afterEach(() => {
      vi.useRealTimers()
    })

    it('is announced immediately but shows no loader during the delay, then the loader', () => {
      render(
        <QueryState {...base} isPending label="Loading users…">
          content
        </QueryState>,
      )
      const status = screen.getByRole('status')
      expect(status.getAttribute('aria-busy')).toBe('true')
      expect(status.textContent).toContain('Loading users…') // sr-only announcement
      expect(screen.queryByTestId('loader')).toBeNull() // nothing visual yet
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(screen.getByTestId('loader')).toBeTruthy()
    })

    it('a query that resolves inside the delay never renders the loader at all', () => {
      const { rerender } = render(
        <QueryState {...base} isPending>
          content
        </QueryState>,
      )
      act(() => {
        vi.advanceTimersByTime(100)
      })
      rerender(<QueryState {...base}>content</QueryState>)
      act(() => {
        vi.advanceTimersByTime(300)
      })
      expect(screen.queryByTestId('loader')).toBeNull()
      expect(screen.getByText('content')).toBeTruthy()
    })

    it('sr-only label defaults to Loading…', () => {
      render(
        <QueryState {...base} isPending>
          content
        </QueryState>,
      )
      expect(screen.getByRole('status').textContent).toContain('Loading…')
    })
  })
})
