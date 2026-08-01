import type { ChapterSummary } from '@/features/library/types'
import type { ServerVoice } from '@/features/reader/api/audioApi'
import type { DownloadProvider } from '@/features/downloads/types'
import { SelectField } from '@/shared/ui'

export function ChapterSelect({
  id,
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  id: string
  label: string
  value: number
  options: ChapterSummary[]
  disabled: boolean
  onChange: (value: number) => void
}) {
  return (
    <SelectField
      id={id}
      label={label}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(Number(event.target.value))}
    >
      {options.map((ch) => (
        <option key={ch.id} value={ch.chapter_number}>
          {ch.chapter_number}. {ch.title || 'Untitled'}
        </option>
      ))}
    </SelectField>
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
  id,
  value,
  voices,
  disabled,
  onChange,
}: {
  id: string
  value: string
  voices: ServerVoice[]
  disabled: boolean
  onChange: (value: string) => void
}) {
  return (
    <SelectField
      id={id}
      label="Voice"
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      {voices.map((voice) => (
        <option key={voice.id} value={voice.id}>
          {voice.name}
        </option>
      ))}
    </SelectField>
  )
}
