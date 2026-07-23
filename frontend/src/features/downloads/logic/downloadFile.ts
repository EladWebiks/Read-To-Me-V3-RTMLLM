/** Trigger a real file download from a URL (avoids browser inline MP3 playback). */
export async function downloadFileFromUrl(url: string, filename: string): Promise<void> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Download failed (${response.status})`)
  }
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}
