import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Button } from '@/shared/ui'
import { MoreControls, PlayerErrorRow } from './PlayerBarExtras'
import { TransportButtons } from './TransportButtons'
import type { SpeechStatus } from '@/features/reader/hooks/useSpeech'

type PlayerBarProps = {
  status: SpeechStatus
  hasText: boolean
  error?: string | null
  autoPlayRequested: boolean
  onSkipPrev: () => void
  onPlayPause: () => void
  onStop: () => void
  onSkipNext: () => void
  rate: number
  volume: number
  onRate: (rate: number) => void
  onVolume: (volume: number) => void
}

export function PlayerBar(props: PlayerBarProps) {
  const [moreOpen, setMoreOpen] = useState(false)
  return (
    <div className="rounded-md border border-border bg-card px-3 py-1">
      <TransportRow
        {...props}
        moreOpen={moreOpen}
        onToggleMore={() => setMoreOpen((v) => !v)}
      />
      <PlayerErrorRow
        error={props.error}
        autoPlayRequested={props.autoPlayRequested}
        status={props.status}
        onPlayPause={props.onPlayPause}
      />
      <MoreControls
        open={moreOpen}
        rate={props.rate}
        volume={props.volume}
        onRate={props.onRate}
        onVolume={props.onVolume}
      />
    </div>
  )
}

function TransportRow(
  props: PlayerBarProps & { moreOpen: boolean; onToggleMore: () => void },
) {
  return (
    <div className="relative flex h-9 items-center justify-center">
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
          aria-expanded={props.moreOpen}
          aria-label="Speed and volume"
          onClick={props.onToggleMore}
        >
          <ChevronDown
            className={`h-4 w-4 transition-transform duration-200 ${
              props.moreOpen ? 'rotate-180' : ''
            }`}
          />
        </Button>
      </div>
    </div>
  )
}
