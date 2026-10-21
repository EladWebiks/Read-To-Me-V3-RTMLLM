/**
 * Brand / atmosphere half of the login split.
 * Uses `public/login-hero.png` when present; falls back to CSS atmosphere.
 * Mobile: shorter band; desktop: full-height panel.
 */
export function LoginBrandPanel() {
  return (
    <section
      className={
        'login-brand relative flex h-[32vh] min-h-[220px] max-h-[300px] ' +
        'flex-col justify-end overflow-hidden px-6 pb-10 pt-8 ' +
        'sm:px-10 lg:h-full lg:max-h-none lg:min-h-full lg:px-12 lg:pb-16 lg:pt-12'
      }
      aria-label="Read To Me"
    >
      <img
        src="/login-hero.png"
        alt=""
        decoding="async"
        className={
          'login-brand-photo pointer-events-none absolute inset-0 h-full w-full ' +
          'object-cover object-[center_70%]'
        }
        onError={(event) => {
          event.currentTarget.hidden = true
        }}
      />
      <div
        className="login-brand-atmosphere pointer-events-none absolute inset-0"
        aria-hidden
      />
      <div className="relative z-[1] max-w-md animate-fade-in-up">
        <img
          src="/Logo-dark.png"
          alt="RTM — Read To Me"
          decoding="async"
          className="h-16 w-auto max-w-[min(100%,22rem)] object-contain object-left drop-shadow-sm sm:h-20 lg:h-24"
        />
        <p className="mt-3 max-w-sm text-sm leading-relaxed opacity-85 sm:text-base lg:mt-4 lg:text-lg">
          Read and listen to your personal library.
        </p>
      </div>
    </section>
  )
}
