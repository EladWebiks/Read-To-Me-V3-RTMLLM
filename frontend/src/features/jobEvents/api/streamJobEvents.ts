import { apiUrl } from '@/shared/lib/api'
import { parseJobEvent } from './parseJobEvent'

export type JobEventKind = 'scrape' | 'download' | 'import'

export type JobEvent = {
  v: 1
  kind: JobEventKind
  job_id: string
  user_id: string
  status: string
  progress: { done: number | null; total: number | null } | null
  book_id: string | null
  updated_at: string
}

type Handlers = {
  onReady: () => void
  onJob: (event: JobEvent) => void
}

/** Consume GET /api/jobs/events until aborted. */
export async function streamJobEvents(
  handlers: Handlers,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(apiUrl('/api/jobs/events'), {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'text/event-stream' },
    signal,
  })
  if (!errorBody(response)) {
    throw new Error(`Job events failed: ${response.status}`)
  }
  await readSse(response.body, handlers, signal)
}

function errorBody(
  response: Response,
): response is Response & { body: ReadableStream<Uint8Array> } {
  return Boolean(response.ok && response.body)
}

async function readSse(
  body: ReadableStream<Uint8Array>,
  handlers: Handlers,
  signal: AbortSignal,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (!signal.aborted) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const block of parts) dispatchBlock(block, handlers)
  }
}

function dispatchBlock(block: string, handlers: Handlers): void {
  const trimmed = block.trim()
  if (!trimmed || trimmed.startsWith(':')) return
  const { event, data } = parseBlock(trimmed)
  if (event === 'ready') {
    handlers.onReady()
    return
  }
  if (event !== 'job' || !data) return
  const parsed = parseJobEvent(data)
  if (parsed) handlers.onJob(parsed)
}

function parseBlock(block: string): { event: string; data: unknown } {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return { event, data: null }
  return { event, data: JSON.parse(dataLines.join('\n')) as unknown }
}
