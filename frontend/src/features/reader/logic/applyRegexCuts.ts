export function applyRegexCuts(
  content: string,
  patterns: string[],
): { cleaned: string; applied: number } {
  let out = content
  let applied = 0
  for (const rawPattern of patterns) {
    const pattern = rawPattern.trim()
    if (!pattern) continue
    try {
      const re = new RegExp(pattern, 'gms')
      out = out.replace(re, '')
      applied += 1
    } catch {
      // Ignore invalid patterns: user can remove/fix them in Settings.
    }
  }
  return { cleaned: out, applied }
}
