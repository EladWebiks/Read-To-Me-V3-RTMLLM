import { AnimatePresence, motion } from 'motion/react'
import { Button } from '@/shared/ui'
import { PlayerControls } from './PlayerControls'
import type { SpeechStatus } from '@/features/reader/hooks/useSpeech'

export function PlayerErrorRow(props: {
  error?: string | null
  autoPlayRequested: boolean
  status: SpeechStatus
  onPlayPause: () => void
}) {
  if (!props.error) return null
  return (
    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm text-destructive">{props.error}</p>
      {props.autoPlayRequested && props.status !== 'playing' ? (
        <Button type="button" variant="outline" size="sm" onClick={props.onPlayPause}>
          Tap to play
        </Button>
      ) : null}
    </div>
  )
}

export function MoreControls(props: {
  open: boolean
  rate: number
  volume: number
  onRate: (rate: number) => void
  onVolume: (volume: number) => void
}) {
  return (
    <AnimatePresence initial={false}>
      {props.open ? (
        <motion.div
          key="player-more"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          className="overflow-hidden"
        >
          <div className="mt-1.5 border-t border-border pb-1 pt-2.5">
            <PlayerControls
              rate={props.rate}
              volume={props.volume}
              onRate={props.onRate}
              onVolume={props.onVolume}
            />
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
