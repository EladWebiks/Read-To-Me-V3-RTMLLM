/** Split chapter text into paragraphs of words. */
export function parseParagraphs(content: string): string[][] {
  return content
    .split(/\n+/)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph.length > 0)
    .map((paragraph) => paragraph.split(/\s+/).filter((word) => word.length > 0))
}

export function clampCursor(
  paragraphs: string[][],
  paragraphIndex: number,
  wordIndex: number,
): { paragraphIndex: number; wordIndex: number } {
  if (paragraphs.length === 0) {
    return { paragraphIndex: 0, wordIndex: 0 }
  }
  const p = Math.min(Math.max(paragraphIndex, 0), paragraphs.length - 1)
  const words = paragraphs[p] ?? []
  if (words.length === 0) {
    return { paragraphIndex: p, wordIndex: 0 }
  }
  return {
    paragraphIndex: p,
    wordIndex: Math.min(Math.max(wordIndex, 0), words.length - 1),
  }
}
