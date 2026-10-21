import { SUPPORTED_SCRAPE_SITES } from '../logic/supportedSites'

/** Clickable list of scrape hosts under the first-chapter URL field. */
export function SupportedSitesLinks() {
  return (
    <p className="text-xs text-muted-foreground">
      {SUPPORTED_SCRAPE_SITES.map((site, index) => (
        <span key={site.name}>
          {index > 0 ? ' · ' : null}
          <a
            href={site.href}
            target="_blank"
            rel="noopener noreferrer"
            className="underline-offset-2 hover:text-foreground hover:underline"
          >
            {site.name}
          </a>
        </span>
      ))}
    </p>
  )
}
