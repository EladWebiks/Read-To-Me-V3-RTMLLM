import { describe, expect, it } from 'vitest'
import { ApiError, apiGet } from '@/shared/lib/api'

describe('api helpers', () => {
  it('exports apiGet', () => {
    expect(typeof apiGet).toBe('function')
  })

  it('ApiError stores status', () => {
    const error = new ApiError(401, 'unauthorized')
    expect(error.status).toBe(401)
    expect(error.message).toBe('unauthorized')
  })
})
