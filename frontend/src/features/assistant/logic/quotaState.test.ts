import { describe, expect, it } from 'vitest'
import type { MeUsage } from '@/features/usage'
import '@/shared/i18n'
import { quotaLock } from './quotaState'

function usage(overrides: Partial<MeUsage['kinds'][number]>[]): MeUsage {
  return {
    membership: 'free',
    membership_label: 'Free',
    exempt: false,
    as_of: '',
    resets_at: '2026-08-01T00:00:00+00:00',
    kinds: overrides.map((o) => ({
      kind: 'llm_tokens',
      label: 'AI tokens',
      unit: 'tokens',
      window: 'month' as const,
      used: 0,
      limit: null,
      ...o,
    })),
  }
}

describe('quotaLock', () => {
  it('locks from a live SSE resets_at regardless of query state', () => {
    expect(quotaLock(undefined, '2026-08-01T00:00:00+00:00')).toContain('resets')
  })
  it('locks when an LLM kind is at/over its limit', () => {
    const lock = quotaLock(usage([{ kind: 'llm_tokens', used: 100, limit: 100 }]), null)
    expect(lock).toContain('Monthly AI limit reached')
  })
  it('stays open under the limit, for unlimited kinds, for exempt users, and for non-LLM kinds', () => {
    expect(quotaLock(usage([{ used: 99, limit: 100 }]), null)).toBeNull()
    expect(quotaLock(usage([{ used: 100, limit: null }]), null)).toBeNull()
    const exempt = { ...usage([{ used: 100, limit: 100 }]), exempt: true }
    expect(quotaLock(exempt, null)).toBeNull()
    expect(
      quotaLock(usage([{ kind: 'audio_chapters', used: 100, limit: 100 }]), null),
    ).toBeNull()
  })
})
