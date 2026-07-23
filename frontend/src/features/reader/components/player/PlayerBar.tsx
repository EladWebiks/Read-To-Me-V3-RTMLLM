import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/shared/ui'
import { PlayerControls } from './PlayerControls'
import { TransportButtons } from './TransportButtons'
import type {
  PlaybackEngine,
  TtsProviderName,
} from '@/features/reader/hooks/ttsSettingsStore'
import type { ServerVoice } from '@/features/reader/api/audioApi'
import type { SpeechStatus } from '@/features/reader/hooks/useSpeech'

type PlayerBarProps = {
  status: SpeechStatus
  hasText: boolean
  error?: string | null
  onSkipPrev: () => void
  onPlayPause: () => void
  onStop: () => void
  onSkipNext: () => void
  engine: PlaybackEngine
  provider: TtsProviderName
  browserVoices: SpeechSynthesisVoice[]
  serverVoices: ServerVoice[]
  voiceURI: string | null
  serverVoice: string | null
  rate: number
  volume: number
  autoNext: boolean
  onEngine: (engine: PlaybackEngine) => void
  onProvider: (provider: TtsProviderName) => void
  onVoice: (voiceURI: string | null) => void
  onServerVoice: (voice: string | null) => void
  onRate: (rate: number) => void
  onVolume: (volume: number) => void
  onAutoNext: (autoNext: boolean) => void
}

export function PlayerBar(props: PlayerBarProps) {
  const [moreOpen, setMoreOpen] = useState(false)
  return (
    <div className="space-y-2 rounded-md border border-border bg-card px-3 py-2">
      <div className="relative flex min-h-10 items-center justify-center">
        <TransportButtons
          status={props.status}
          hasText={props.hasText}
          onSkipPrev={props.onSkipPrev}
          onPlayPause={props.onPlayPause}
          onStop={props.onStop}
          onSkipNext={props.onSkipNext}
        />
        <div className="absolute right-0 flex items-center gap-1">
          <span className="hidden text-xs capitalize text-muted-foreground sm:inline">
            {props.status}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="More playback settings"
            onClick={() => setMoreOpen((v) => !v)}
          >
            {moreOpen ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
      {props.error ? <p className="text-sm text-destructive">{props.error}</p> : null}
      {moreOpen ? <PlayerControls {...props} /> : null}
    </div>
  )
}
