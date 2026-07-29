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
      engine={settings.engine}
      provider={settings.provider}
      browserVoices={reader.browserVoices}
      serverVoices={reader.serverVoices}
      voiceURI={settings.voiceURI}
      serverVoice={settings.serverVoice}
      rate={settings.rate}
      volume={settings.volume}
      autoNext={settings.autoNext}
      onEngine={settings.setEngine}
      onProvider={settings.setProvider}
      onVoice={settings.setVoiceURI}
      onServerVoice={settings.setServerVoice}
      onRate={settings.setRate}
      onVolume={settings.setVolume}
      onAutoNext={settings.setAutoNext}
    />
  )
}
