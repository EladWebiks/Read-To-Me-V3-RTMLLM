/** Pause and detach the offline player audio element. */
export function stopListenAudio(audioRef: { current: HTMLAudioElement | null }): void {
  const audio = audioRef.current
  if (!audio) return
  audio.onended = null
  audio.onerror = null
  audio.ontimeupdate = null
  audio.onloadedmetadata = null
  audio.pause()
  audio.removeAttribute('src')
  audio.load()
  audioRef.current = null
}

export function formatListenTime(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
