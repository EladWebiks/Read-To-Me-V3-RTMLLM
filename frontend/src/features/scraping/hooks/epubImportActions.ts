import type { useQueryClient } from '@tanstack/react-query'
import { cancelImport, importEpub } from '../api/importApi'
import type { EpubImportResult, ImportJob } from '../types/importTypes'

export function moveFileItem(prev: File[], index: number, direction: -1 | 1): File[] {
  const target = index + direction
  if (target < 0 || target >= prev.length) return prev
  const next = [...prev]
  const a = next[index]
  const b = next[target]
  if (!a || !b) return prev
  next[index] = b
  next[target] = a
  return next
}

type StartArgs = {
  files: File[]
  importing: boolean
  title: string
  author: string
  startingChapter: string
  setImportError: (e: string) => void
  setResult: (r: EpubImportResult | null) => void
  setCancelling: (v: boolean) => void
  setImportStartedAt: (n: number | null) => void
  setElapsedMs: (n: number) => void
  setImportJob: (j: ImportJob | null) => void
  queryClient: ReturnType<typeof useQueryClient>
  onImported: () => void
}

export async function startEpubImport(args: StartArgs): Promise<void> {
  if (args.files.length === 0 || args.importing) return
  args.setImportError('')
  args.setResult(null)
  args.setCancelling(false)
  args.setImportStartedAt(Date.now())
  args.setElapsedMs(0)
  try {
    await kickoffImport(args)
  } catch (err) {
    args.setImportStartedAt(null)
    args.setImportError(err instanceof Error ? err.message : 'Import failed')
  }
}

async function kickoffImport(args: StartArgs): Promise<void> {
  const startNum = args.startingChapter ? parseInt(args.startingChapter, 10) : 1
  const job = await importEpub(args.files, {
    title: args.title.trim() || undefined,
    author: args.author.trim() || undefined,
    startingChapter: Number.isFinite(startNum) && startNum >= 1 ? startNum : 1,
  })
  args.setImportJob(job)
  if (job.status === 'completed' && job.result) {
    args.setResult(job.result)
    void args.queryClient.invalidateQueries({ queryKey: ['library', 'books'] })
    args.onImported()
  } else if (job.status === 'failed') {
    args.setImportError(job.message || 'Import failed')
  }
}

export async function cancelEpubImport(
  importJob: ImportJob | null,
  importing: boolean,
  setCancelling: (v: boolean) => void,
  setImportJob: (j: ImportJob) => void,
  setImportError: (e: string) => void,
): Promise<void> {
  if (!importJob || !importing) return
  setCancelling(true)
  try {
    const job = await cancelImport(importJob.job_id)
    setImportJob(job)
    if (job.status === 'cancelled') setImportError(job.message || 'Import cancelled')
  } catch (err) {
    setImportError(err instanceof Error ? err.message : 'Failed to cancel import')
  } finally {
    setCancelling(false)
  }
}
