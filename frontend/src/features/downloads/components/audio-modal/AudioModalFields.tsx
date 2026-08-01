import type { ChapterSummary } from '@/features/library/types'
import type { ServerVoice } from '@/features/reader/api/audioApi'
import type { AudioFormState } from '@/features/downloads/logic/audioModalUtils'
import { sortedChapters } from '@/features/downloads/logic/audioModalUtils'
import { useAppSettings } from '@/features/settings/settingsStore'
import { ChapterSelect, ProviderToggle, VoiceSelect } from './AudioModalSelects'

type Props = {
  chapters: ChapterSummary[]
  form: AudioFormState
  voices: ServerVoice[]
  busy: boolean
  onChange: (patch: Partial<AudioFormState>) => void
}

export function AudioModalFields({ chapters, form, voices, busy, onChange }: Props) {
  const maxRate = useAppSettings((s) => s.maxRate)
  const sorted = sortedChapters(chapters)
  const endOptions = sorted.filter((ch) => ch.chapter_number >= form.from)
  return (
    <div className="space-y-3 text-sm">
      <ChapterSelect
        id="download-from-chapter"
        label="From chapter"
        value={form.from}
        options={sorted}
        disabled={busy}
        onChange={(from) => onChange({ from, to: Math.max(from, form.to) })}
      />
      <ChapterSelect
        id="download-to-chapter"
        label="To chapter"
        value={form.to}
        options={endOptions}
        disabled={busy}
        onChange={(to) => onChange({ to })}
      />
      <ProviderToggle
        value={form.provider}
        disabled={busy}
        onChange={(provider) => onChange({ provider })}
      />
      {form.provider === 'edge' ? (
        <VoiceSelect
          id="download-voice"
          value={form.voice}
          voices={voices}
          disabled={busy}
          onChange={(voice) => onChange({ voice })}
        />
      ) : (
        <p className="text-muted-foreground">Voice: Microsoft Zira Desktop</p>
      )}
      <label className="flex flex-col gap-1">
        <span>Speed: {form.rate.toFixed(2)}x</span>
        <input
          type="range"
          min={0.5}
          max={maxRate}
          step={0.05}
          value={form.rate}
          disabled={busy}
          onChange={(event) => onChange({ rate: Number(event.target.value) })}
        />
      </label>
    </div>
  )
}
