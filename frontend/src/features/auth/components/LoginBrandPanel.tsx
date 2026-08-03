/**
 * Brand / atmosphere half of the login split.
 * Drop `frontend/public/login-hero.png` (or .jpg) to activate the photo layer.
 */
export function LoginBrandPanel() {
  return (
    <section
      className="login-brand relative flex min-h-[38vh] flex-col justify-end overflow-hidden p-8 sm:min-h-0 sm:p-12 lg:p-16"
      aria-label="Read To Me"
    >
      <LoginHeroImage />
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

function LoginHeroImage() {
  return (
    <img
      src="/login-hero.png"
      alt=""
      decoding="async"
      className="login-brand-photo pointer-events-none absolute inset-0 h-full w-full object-cover object-[center_70%]"
      onError={(event) => {
        event.currentTarget.hidden = true
      }}
    />
  )
}
