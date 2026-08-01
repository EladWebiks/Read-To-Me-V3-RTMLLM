import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { MeUsageKind } from '../api/meUsage'
import { MeterRow } from './MeterRow'

const zeroLimit: MeUsageKind = {
  kind: 'llm_tokens',
  label: 'AI tokens',
  unit: 'tokens',
  window: 'month',
  used: 0,
  limit: 0,
}

// vitest runs with globals:false, so testing-library's auto-cleanup is not registered.
afterEach(cleanup)

describe('MeterRow', () => {
  it('shows a 0 limit as spent, not as unlimited', () => {
    render(<MeterRow kind={zeroLimit} />)
    expect(screen.getByText('0 / 0')).toBeTruthy()
    expect(screen.queryByText(/Unlimited/)).toBeNull()
    expect(screen.getByRole('progressbar').getAttribute('data-state')).toBe('over')
  })

  it('draws no bar when the limit really is unlimited', () => {
    render(<MeterRow kind={{ ...zeroLimit, limit: null }} />)
    expect(screen.getByText('0 · Unlimited')).toBeTruthy()
    expect(screen.queryByRole('progressbar')).toBeNull()
  })
})
