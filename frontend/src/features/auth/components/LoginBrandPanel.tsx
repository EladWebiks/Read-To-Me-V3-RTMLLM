/**
 * Brand / atmosphere half of the login split.
 * When you have art, put it at `public/login-hero.png` and we can wire it —
 * do not drop random files into public expecting them to auto-bind.
 */
export function LoginBrandPanel() {
  return (
    <section
      className="login-brand relative flex h-full min-h-[42vh] flex-col justify-end overflow-hidden p-8 sm:p-12 lg:min-h-full lg:p-16"
      aria-label="Read To Me"
    >
      <div
        className="login-brand-atmosphere pointer-events-none absolute inset-0"
        aria-hidden
      />
      <div className="relative z-[1] max-w-md animate-fade-in-up">
        <p className="login-brand-mark text-5xl tracking-tight sm:text-6xl lg:text-7xl">
          RTM
        </p>
        <p className="mt-3 max-w-sm text-base leading-relaxed opacity-85 sm:text-lg">
          Read and listen to your personal library.
        </p>
      </div>
    </section>
  )
}
