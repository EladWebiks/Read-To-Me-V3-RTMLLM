import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiGet, apiPut } from '@/shared/lib/api'

/** A Response stub; `body: undefined` stands in for a non-JSON payload. */
function respondWith(status: number, body?: unknown) {
  const json = async () => {
    if (body === undefined) throw new SyntaxError('Unexpected token < in JSON')
    return body
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: status < 400, status, json }) as unknown as Response),
  )
}

async function rejectionOf(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    if (error instanceof ApiError) return error
    throw error
  }
  throw new Error('expected the request to reject, but it resolved')
}

afterEach(() => vi.unstubAllGlobals())

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

describe('api error detail', () => {
  it('names the field and reason from a pydantic 422 body', async () => {
    respondWith(422, {
      detail: [
        {
          type: 'greater_than_equal',
          loc: ['body', 'limit_value'],
          msg: 'Input should be greater than or equal to 0',
          input: -1,
        },
      ],
    })
    const error = await rejectionOf(
      apiPut('/api/admin/membership-quotas/free/llm_cost_usd'),
    )
    expect(error.status).toBe(422)
    expect(error.message).toBe('limit_value: Input should be greater than or equal to 0')
  })

  it('joins every validation item so none is hidden', async () => {
    respondWith(422, {
      detail: [
        { loc: ['body', 'limit_value'], msg: 'Input should be a valid number' },
        { loc: ['path', 'kind'], msg: 'Input should be a valid enumeration member' },
      ],
    })
    const error = await rejectionOf(apiPut('/api/admin/membership-quotas/free/nope'))
    expect(error.message).toBe(
      'limit_value: Input should be a valid number; kind: Input should be a valid enumeration member',
    )
  })

  it('keeps a plain string detail from a domain error', async () => {
    respondWith(404, { detail: 'Membership tier platinum was not found' })
    const error = await rejectionOf(
      apiPut('/api/admin/membership-quotas/platinum/llm_tokens'),
    )
    expect(error.message).toBe('Membership tier platinum was not found')
  })

  it('falls back to the status when the body is not JSON', async () => {
    respondWith(500)
    const error = await rejectionOf(apiGet('/api/admin/membership-quotas'))
    expect(error.message).toBe('Request failed: 500')
  })

  it('falls back to the status when detail has an unknown shape', async () => {
    respondWith(400, { detail: { unexpected: true } })
    const error = await rejectionOf(apiGet('/api/admin/membership-quotas'))
    expect(error.message).toBe('Request failed: 400')
  })
})
