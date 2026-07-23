import { useSyncExternalStore } from 'react'

let cachedVoices: SpeechSynthesisVoice[] = []

function subscribe(onChange: () => void): () => void {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    return () => undefined
  }
  const sync = () => {
    cachedVoices = window.speechSynthesis.getVoices()
    onChange()
  }
  sync()
  window.speechSynthesis.addEventListener('voiceschanged', sync)
  return () => {
    window.speechSynthesis.removeEventListener('voiceschanged', sync)
  }
}

function getSnapshot(): SpeechSynthesisVoice[] {
  return cachedVoices
}

function getServerSnapshot(): SpeechSynthesisVoice[] {
  return []
}

export function useVoices(): SpeechSynthesisVoice[] {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
