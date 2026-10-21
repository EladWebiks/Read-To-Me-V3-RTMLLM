import type {
  ChoiceOption,
  ChoicePayload,
  ClientAction,
  ConfirmationPayload,
  UiSettingsPatch,
} from './chatTypes'

export function parseClientAction(raw: unknown): ClientAction | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const obj = raw as Record<string, unknown>
  const path = obj.path
  const label = obj.label
  const type = obj.type
  if (typeof label !== 'string' || typeof type !== 'string') {
    return undefined
  }
  if (type === 'settings' && obj.settings && typeof obj.settings === 'object') {
    return { type, label, settings: obj.settings as UiSettingsPatch }
  }
  if (
    type === 'download' &&
    typeof obj.job_id === 'string' &&
    typeof obj.book_id === 'string' &&
    typeof obj.chapter_from === 'number' &&
    typeof obj.chapter_to === 'number'
  ) {
    return {
      type,
      label,
      jobId: obj.job_id,
      bookId: obj.book_id,
      chapterFrom: obj.chapter_from,
      chapterTo: obj.chapter_to,
    }
  }
  if (type === 'scrape' && typeof obj.job_id === 'string') {
    return {
      type,
      label,
      jobId: obj.job_id,
      maxChapters: typeof obj.max_chapters === 'number' ? obj.max_chapters : null,
      chapterFrom: typeof obj.chapter_from === 'number' ? obj.chapter_from : null,
    }
  }
  if (type !== 'navigate' && type !== 'play') return undefined
  if (typeof path !== 'string') return undefined
  if (!path.startsWith('/')) return undefined
  return { type, path, label }
}

export function parseChoice(data: Record<string, unknown>): ChoicePayload | null {
  const raw = data.options
  if (!Array.isArray(raw)) return null
  const options: ChoiceOption[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const row = item as Record<string, unknown>
    const id = typeof row.id === 'string' ? row.id : ''
    const label = typeof row.label === 'string' ? row.label.trim() : ''
    if (id && label) options.push({ id, label })
  }
  if (options.length < 2) return null
  const prompt =
    typeof data.prompt === 'string' && data.prompt.trim()
      ? data.prompt.trim()
      : 'Choose one:'
  return { prompt, options }
}

export function parseConfirmation(data: Record<string, unknown>): ConfirmationPayload {
  const formRaw = data.form
  const form =
    formRaw && typeof formRaw === 'object'
      ? (formRaw as ConfirmationPayload['form'])
      : null
  return {
    callId: String(data.call_id ?? ''),
    tool: String(data.tool ?? ''),
    risk: String(data.risk ?? ''),
    summary: String(data.summary ?? 'Confirm action'),
    action: optionalString(data.action),
    title: optionalString(data.title),
    subtitle: optionalString(data.subtitle),
    args: (data.args as Record<string, unknown>) ?? {},
    form,
    status: 'pending',
  }
}

function optionalString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

export function parseSseBlock(block: string): {
  event: string
  data: Record<string, unknown> | null
} {
  const lines = block.split('\n')
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return { event, data: null }
  return { event, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> }
}
