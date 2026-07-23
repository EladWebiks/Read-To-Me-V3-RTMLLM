type AudioRef = { current: HTMLAudioElement | null }
type UrlRef = { current: string | null }
type SettleRef = { current: (() => void) | null }

export function stopAudio(
  audioRef: AudioRef,
  urlRef: UrlRef,
  settleRef?: SettleRef,
): void {
  const settle = settleRef?.current
  if (settleRef) {
    settleRef.current = null
  }
  if (audioRef.current) {
    const audio = audioRef.current
    audio.onended = null
    audio.onerror = null
    audio.pause()
    audio.removeAttribute('src')
    audio.load()
    audioRef.current = null
  }
  if (urlRef.current) {
    URL.revokeObjectURL(urlRef.current)
    urlRef.current = null
  }
  settle?.()
}

export function playBlob(
  blob: Blob,
  volume: number,
  audioRef: AudioRef,
  urlRef: UrlRef,
  settleRef: SettleRef,
  cancelledRef: { current: boolean },
): Promise<void> {
  return new Promise((resolve, reject) => {
    stopAudio(audioRef, urlRef, settleRef)
    const url = URL.createObjectURL(blob)
    urlRef.current = url
    const audio = new Audio(url)
    audio.volume = volume
    audioRef.current = audio
    settleRef.current = () => resolve()
    audio.onended = () => {
      settleRef.current = null
      resolve()
    }
    audio.onerror = () => {
      settleRef.current = null
      if (cancelledRef.current) {
        resolve()
        return
      }
      reject(new Error('audio playback failed'))
    }
    void audio.play().catch((error: unknown) => {
      settleRef.current = null
      if (cancelledRef.current) {
        resolve()
        return
      }
      reject(error instanceof Error ? error : new Error('audio playback failed'))
    })
  })
}
