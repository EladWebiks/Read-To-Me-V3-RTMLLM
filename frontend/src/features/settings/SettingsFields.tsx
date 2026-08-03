import { useAppSettings } from './settingsStore'
import { Button } from '@/shared/ui'
import { RangeRow, SettingLabel } from './SettingsControls'
import { SettingsPlaybackFields } from './SettingsPlaybackFields'

export function SettingsFields() {
  const fontSize = useAppSettings((s) => s.fontSize)
  const highlightMode = useAppSettings((s) => s.highlightMode)
  const setFontSize = useAppSettings((s) => s.setFontSize)
  const setHighlightMode = useAppSettings((s) => s.setHighlightMode)
  return (
    <div className="space-y-5 text-sm">
      <RangeRow
        id="font-size"
        label={`Reader font size (${fontSize.toFixed(2)}rem)`}
        tip="Size of chapter text in the reader."
        min={1}
        max={1.8}
        step={0.05}
        value={fontSize}
        onChange={setFontSize}
      />
      <div className="space-y-2">
        <SettingLabel
          label="Highlight mode"
          tip="How the reader marks the active text while listening: word, paragraph, or auto."
        />
        <div className="flex flex-wrap gap-2">
          {(['auto', 'word', 'paragraph'] as const).map((mode) => (
            <Button
              key={mode}
              type="button"
              size="sm"
              variant={highlightMode === mode ? 'default' : 'outline'}
              onClick={() => setHighlightMode(mode)}
            >
              {mode}
            </Button>
          ))}
        </div>
      </div>
      <SettingsPlaybackFields />
    </div>
  )
}
