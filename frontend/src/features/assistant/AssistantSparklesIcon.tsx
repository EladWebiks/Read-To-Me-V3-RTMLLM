/** Colorful sparkles mark for the LLM assistant (navbar only). */
export function AssistantSparklesIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className ?? 'h-6 w-6'}
    >
      <g className="assistant-spark-a origin-center">
        <path
          d="M12 2.4 13.4 7.5 18.4 8.8 13.4 10.1 12 15.2 10.6 10.1 5.6 8.8 10.6 7.5 12 2.4Z"
          fill="url(#rtm-ai-grad-a)"
        />
      </g>
      <g className="assistant-spark-b origin-center">
        <path
          d="M19 11.2 19.85 14.1 18 15.5 20.7 16.25 19 18.9 17.3 16.25 20 15.5 18.15 14.1 19 11.2Z"
          fill="url(#rtm-ai-grad-b)"
        />
      </g>
      <g className="assistant-spark-c origin-center">
        <path
          d="M5.6 12.8 6.4 15.2 4.7 16.4 7.1 17.05 5.6 19.4 4.1 17.05 6.5 16.4 4.8 15.2 5.6 12.8Z"
          fill="url(#rtm-ai-grad-c)"
        />
      </g>
      <defs>
        <linearGradient id="rtm-ai-grad-a" x1="5.6" y1="2.4" x2="18.4" y2="15.2">
          <stop stopColor="#6366f1" />
          <stop offset="0.5" stopColor="#a855f7" />
          <stop offset="1" stopColor="#ec4899" />
        </linearGradient>
        <linearGradient id="rtm-ai-grad-b" x1="18" y1="11.2" x2="20.7" y2="18.9">
          <stop stopColor="#22d3ee" />
          <stop offset="1" stopColor="#6366f1" />
        </linearGradient>
        <linearGradient id="rtm-ai-grad-c" x1="4.7" y1="12.8" x2="7.1" y2="19.4">
          <stop stopColor="#fbbf24" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
      </defs>
    </svg>
  )
}
