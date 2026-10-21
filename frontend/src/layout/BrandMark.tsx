import { Link } from 'react-router'

/** App header brand — wordmark; swaps to a light variant in dark mode. */
export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <Link
      to="/library"
      className={`inline-flex shrink-0 items-center ${className}`.trim()}
      aria-label="RTM — Read To Me"
    >
      <img
        src="/Logo.png"
        alt=""
        decoding="async"
        className="h-11 w-auto object-contain object-left dark:hidden sm:h-12"
      />
      <img
        src="/Logo-dark.png"
        alt=""
        decoding="async"
        className="hidden h-11 w-auto object-contain object-left dark:block sm:h-12"
      />
    </Link>
  )
}
