import { useTheme } from 'next-themes'
import { useAppSettings } from './settingsStore'
import { Button, Label } from '@/shared/ui'
import { RangeRow, ThemeButtons } from './SettingsControls'

export function SettingsFields() {
  const { theme, setTheme } = useTheme()
  const fontSize = useAppSettings((s) => s.fontSize)
  const maxRate = useAppSettings((s) => s.maxRate)
  const highlightMode = useAppSettings((s) => s.highlightMode)
  const setFontSize = useAppSettings((s) => s.setFontSize)
  const setMaxRate = useAppSettings((s) => s.setMaxRate)
  const setHighlightMode = useAppSettings((s) => s.setHighlightMode)
  return (
    <div className="space-y-5 text-sm">
      <div className="space-y-2">
        <Label>Theme</Label>
        <ThemeButtons theme={theme} setTheme={setTheme} />
      </div>
      <RangeRow
        id="font-size"
        label={`Reader font size (${fontSize.toFixed(2)}rem)`}
        min={1}
        max={1.8}
        step={0.05}
        value={fontSize}
        onChange={setFontSize}
      />
      <RangeRow
        id="max-rate"
        label={`Max TTS speed (${maxRate.toFixed(1)}x)`}
        min={1}
        max={4}
        step={0.1}
        value={maxRate}
        onChange={setMaxRate}
      />
      <div className="space-y-2">
        <Label>Highlight mode</Label>
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
    </div>
  )
}
