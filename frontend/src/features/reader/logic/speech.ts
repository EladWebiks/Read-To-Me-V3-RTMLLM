/** Map a SpeechSynthesis boundary charIndex to a word index in a paragraph. */
export function charIndexToWordIndex(words: string[], charIndex: number): number {
  if (words.length === 0) {
    return 0
  }
  let offset = 0
  for (let i = 0; i < words.length; i += 1) {
    const word = words[i] ?? ''
    const next = offset + word.length
    if (charIndex < next || i === words.length - 1) {
      return i
    }
    offset = next + 1
  }
  return words.length - 1
}

export function paragraphText(words: string[]): string {
  return words.join(' ')
}

export type UtteranceOptions = {
  text: string
  rate: number
  volume: number
  voice: SpeechSynthesisVoice | null
}

export function buildUtterance(options: UtteranceOptions): SpeechSynthesisUtterance {
  const utterance = new SpeechSynthesisUtterance(options.text)
  utterance.rate = options.rate
  utterance.volume = options.volume
  if (options.voice) {
    utterance.voice = options.voice
  }
  return utterance
}
