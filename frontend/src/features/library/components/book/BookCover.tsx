type Props = { url: string | null; title: string }

const PALETTE = [
  'from-stone-600 to-stone-800',
  'from-sky-600 to-slate-800',
  'from-teal-600 to-emerald-900',
  'from-amber-600 to-orange-900',
  'from-rose-600 to-red-900',
  'from-indigo-600 to-violet-900',
]

function gradientFor(title: string): string {
  let hash = 0
  for (let i = 0; i < title.length; i += 1) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash)
  }
  return PALETTE[Math.abs(hash) % PALETTE.length]!
}

export function BookCover({ url, title }: Props) {
  if (url) {
    return (
      <img src={url} alt="" className="absolute inset-0 h-full w-full object-cover" />
    )
  }
  const initials = title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
  return (
    <div
      className={`absolute inset-0 flex items-center justify-center bg-gradient-to-br text-lg font-semibold tracking-wide text-white/85 ${gradientFor(title)}`}
      aria-hidden
    >
      {initials || '·'}
    </div>
  )
}
