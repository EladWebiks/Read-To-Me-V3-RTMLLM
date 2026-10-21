import type { ChatUiLang } from '@/shared/lib/textDirection'
import i18n from '@/shared/i18n'

/** Composer placeholder copy, most-blocking reason first. */
export function composerPlaceholder(
  quotaNotice: string | null,
  blocked: boolean,
  sending: boolean,
  status: string | null,
  lng: ChatUiLang = 'en',
): string {
  if (quotaNotice) return quotaNotice
  if (blocked) return i18n.t('assistant:composer.waitingConfirm', { lng })
  if (sending) return status || i18n.t('assistant:composer.working', { lng })
  return i18n.t('assistant:composer.placeholder', { lng })
}
