import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import { useServerVoices } from '@/features/reader/hooks/useServerVoices'
import { useVoices } from '@/features/reader/hooks/useVoices'
import { AutoAdvanceField, EngineFields } from './SettingsEngineFields'
import { SettingsVoiceField } from './SettingsVoiceField'

/** Engine, voice, and chapter auto-advance — live in Settings, not the reader bar. */
export function SettingsPlaybackFields() {
  const engine = useTtsSettings((s) => s.engine)
  const provider = useTtsSettings((s) => s.provider)
  const voiceURI = useTtsSettings((s) => s.voiceURI)
  const serverVoice = useTtsSettings((s) => s.serverVoice)
  const autoNext = useTtsSettings((s) => s.autoNext)
  const setEngine = useTtsSettings((s) => s.setEngine)
  const setProvider = useTtsSettings((s) => s.setProvider)
  const setVoiceURI = useTtsSettings((s) => s.setVoiceURI)
  const setServerVoice = useTtsSettings((s) => s.setServerVoice)
  const setAutoNext = useTtsSettings((s) => s.setAutoNext)
  const browserVoices = useVoices()
  const serverVoices = useServerVoices(provider)

  return (
    <div className="space-y-4 border-t border-border pt-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Listening
      </p>
      <EngineFields
        engine={engine}
        provider={provider}
        onEngine={setEngine}
        onProvider={setProvider}
      />
      <SettingsVoiceField
        engine={engine}
        voiceURI={voiceURI}
        serverVoice={serverVoice}
        browserVoices={browserVoices}
        serverVoices={serverVoices.data ?? []}
        loading={Boolean(serverVoices.isLoading)}
        onBrowserVoice={setVoiceURI}
        onServerVoice={setServerVoice}
      />
      <AutoAdvanceField checked={autoNext} onChange={setAutoNext} />
    </div>
  )
}
