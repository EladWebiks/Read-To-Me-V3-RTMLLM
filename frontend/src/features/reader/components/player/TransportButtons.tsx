import { Pause, Play, SkipBack, SkipForward, Square } from 'lucide-react'
import { Button } from '@/shared/ui'
import type { SpeechStatus } from '@/features/reader/hooks/useSpeech'

type Props = {
  status: SpeechStatus
  hasText: boolean
  onSkipPrev: () => void
  onPlayPause: () => void
  onStop: () => void
  onSkipNext: () => void
}

export function TransportButtons(props: Props) {
  const playing = props.status === 'playing'
  const idle = props.status === 'idle'
  return (
    <div className="flex items-center gap-0.5">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Previous paragraph"
        title="Previous paragraph"
        disabled={!props.hasText}
        onClick={props.onSkipPrev}
      >
        <SkipBack className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        size="icon"
        className="mx-0.5 h-10 w-10 rounded-full"
        aria-label={playing ? 'Pause' : 'Play'}
        title={playing ? 'Pause' : props.status === 'paused' ? 'Resume' : 'Play'}
        disabled={!props.hasText}
        onClick={props.onPlayPause}
      >
        {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Stop"
        title="Stop"
        disabled={idle}
        onClick={props.onStop}
      >
        <Square className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Next paragraph"
        title="Next paragraph"
        disabled={!props.hasText}
        onClick={props.onSkipNext}
      >
        <SkipForward className="h-4 w-4" />
      </Button>
    </div>
  )
}
