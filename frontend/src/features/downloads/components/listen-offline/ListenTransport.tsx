import { Button } from '@/shared/ui'
import { formatListenTime } from '@/features/downloads/logic/listenAudioUtils'
import type { ListenControlsProps } from '@/features/downloads/logic/listenControlsTypes'

export function ListenScrubber(props: ListenControlsProps) {
  const max = props.duration > 0 ? props.duration : Math.max(props.currentTime, 1)
  return (
    <div className="space-y-1">
      <input
        type="range"
        className="w-full"
        min={0}
        max={max}
        step={0.1}
        value={Math.min(props.currentTime, max)}
        disabled={!props.duration && !props.currentTime}
        onChange={(e) => props.onSeekTo(Number(e.target.value))}
        aria-label="Chapter progress"
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{formatListenTime(props.currentTime)}</span>
        <span>{formatListenTime(props.duration)}</span>
      </div>
    </div>
  )
}

export function ListenTransport(props: ListenControlsProps) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={!props.chapterReady}
        onClick={props.onSeekBack}
      >
        −20s
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!props.canPrev}
        onClick={props.onPrev}
      >
        Prev
      </Button>
      {props.status === 'playing' ? (
        <Button size="sm" onClick={props.onPause}>
          Pause
        </Button>
      ) : (
        <Button
          size="sm"
          disabled={!props.chapterReady || props.status === 'loading'}
          onClick={props.onResume}
        >
          {props.status === 'loading' ? 'Loading…' : 'Play'}
        </Button>
      )}
      <Button
        variant="outline"
        size="sm"
        disabled={!props.canNext}
        onClick={props.onNext}
      >
        Next
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!props.chapterReady}
        onClick={props.onSeekForward}
      >
        +20s
      </Button>
    </div>
  )
}
