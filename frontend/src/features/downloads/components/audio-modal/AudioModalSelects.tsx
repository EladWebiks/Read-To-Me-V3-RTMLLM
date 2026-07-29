import type { ChapterSummary } from '@/features/library/types'
import type { ServerVoice } from '@/features/reader/api/audioApi'
import type { DownloadProvider } from '@/features/downloads/types'

export function ChapterSelect({
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  label: string
  value: number
  options: ChapterSummary[]
  disabled: boolean
  onChange: (value: number) => void
}) {
  return (
    <label className="flex flex-col gap-1">
      {label}
      <select
        className="rounded-md border border-border bg-background px-2 py-1.5 text-foreground"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      >
        {options.map((ch) => (
          <option key={ch.id} value={ch.chapter_number}>
            {ch.chapter_number}. {ch.title || 'Untitled'}
          </option>
        ))}
      </select>
    </label>
  )
}

export function ProviderToggle({
  value,
  disabled,
  onChange,
}: {
  value: DownloadProvider
  disabled: boolean
  onChange: (value: DownloadProvider) => void
}) {
  return (
    <div className="flex overflow-hidden rounded-md border border-border">
      {(['sapi', 'edge'] as const).map((provider) => (
        <button
          key={provider}
          type="button"
          disabled={disabled}
          className={`flex-1 px-3 py-2 ${
            value === provider
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-foreground hover:bg-muted'
          }`}
          onClick={() => onChange(provider)}
        >
          {provider === 'sapi' ? 'Zira (SAPI)' : 'Edge (Neural)'}
        </button>
      ))}
    </div>
  )
}

export function VoiceSelect({
  value,
  voices,
  disabled,
  onChange,
}: {
  value: string
  voices: ServerVoice[]
  disabled: boolean
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-col gap-1">
      Voice
      <select
        className="rounded-md border border-border bg-background px-2 py-1.5 text-foreground"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {voices.map((voice) => (
          <option key={voice.id} value={voice.id}>
            {voice.name}
          </option>
        ))}
      </select>
    </label>
  )
}
