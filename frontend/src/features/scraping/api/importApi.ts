import { ApiError } from '@/shared/lib/api'
import type { EpubImportOptions, ImportJob } from '../types/importTypes'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

type PreparedUpload = {
  upload_id: string
  filename: string
  size: number
  chunk_size: number
  total_chunks: number
}

async function readImport<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    const detail =
      body.detail ||
      (res.status === 413
        ? 'Upload chunk rejected as too large — try again after updating the app.'
        : `Request failed: ${res.status}`)
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

/** Upload files in 512KiB chunks, then start the import job. */
export async function importEpub(
  files: File[],
  opts: EpubImportOptions = {},
): Promise<ImportJob> {
  const uploadIds: string[] = []
  for (const file of files) {
    uploadIds.push(await uploadFileChunked(file))
  }
  return fetch(`${API_BASE}/api/import/epub/start`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      upload_ids: uploadIds,
      title: opts.title?.trim() || undefined,
      author: opts.author?.trim() || undefined,
      starting_chapter:
        opts.startingChapter != null && opts.startingChapter >= 1
          ? opts.startingChapter
          : 1,
    }),
  }).then((r) => readImport<ImportJob>(r))
}

async function uploadFileChunked(file: File): Promise<string> {
  const prepared = await fetch(`${API_BASE}/api/import/epub/uploads`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: file.name, size: file.size }),
  }).then((r) => readImport<PreparedUpload>(r))

  for (let index = 0; index < prepared.total_chunks; index += 1) {
    const start = index * prepared.chunk_size
    const end = Math.min(start + prepared.chunk_size, file.size)
    const chunk = file.slice(start, end)
    const res = await fetch(
      `${API_BASE}/api/import/epub/uploads/${prepared.upload_id}/chunks/${index}`,
      {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: chunk,
      },
    )
    await readImport(res)
  }

  await fetch(`${API_BASE}/api/import/epub/uploads/${prepared.upload_id}/complete`, {
    method: 'POST',
    credentials: 'include',
  }).then((r) => readImport(r))

  return prepared.upload_id
}

export function getImportJob(jobId: string): Promise<ImportJob> {
  return fetch(`${API_BASE}/api/import/${jobId}`, { credentials: 'include' }).then((r) =>
    readImport<ImportJob>(r),
  )
}

export function cancelImport(jobId: string): Promise<ImportJob> {
  return fetch(`${API_BASE}/api/import/${jobId}/cancel`, {
    method: 'POST',
    credentials: 'include',
  }).then((r) => readImport<ImportJob>(r))
}
