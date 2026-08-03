import { PlayerBar } from './PlayerBar'
import type { useChapterReader } from '@/features/reader/hooks/useChapterReader'

type ReaderPlayerProps = {
  reader: ReturnType<typeof useChapterReader>
  autoPlayRequested?: boolean
}

export function ReaderPlayer({ reader, autoPlayRequested = false }: ReaderPlayerProps) {
  const { settings } = reader
  return (
    <PlayerBar
      status={reader.status}
      hasText={reader.paragraphs.length > 0}
      error={reader.error}
      autoPlayRequested={autoPlayRequested}
      onSkipPrev={reader.skipPrev}
      onPlayPause={reader.playPause}
      onStop={reader.stop}
      onSkipNext={reader.skipNext}
      rate={settings.rate}
      volume={settings.volume}
      onRate={settings.setRate}
      onVolume={settings.setVolume}
    />
  )
}
