import { X } from 'lucide-react'
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import type { LinkSafetyModalProps } from 'streamdown'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import { textDirForLang } from '@/shared/lib/textDirection'
import { LinkSafetyActions, LinkSafetyHeader } from './linkSafetyParts'

type Props = LinkSafetyModalProps & { uiLang: ChatUiLang }

/** Portaled above the assistant panel; closes after copy or visit. */
export function ExternalLinkSafetyModal(props: Props) {
  const { isOpen, onClose } = props
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])
  if (!isOpen) return null
  return createPortal(
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/45 p-4"
      role="presentation"
      onClick={onClose}
    >
      <LinkSafetyCard {...props} />
    </div>,
    document.body,
  )
}

function LinkSafetyCard({ onClose, onConfirm, url, uiLang }: Props) {
  const { t } = useTranslation('assistant', { lng: uiLang })
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ext-link-title"
      dir={textDirForLang(uiLang)}
      className="relative w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl"
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className="absolute end-3 top-3 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        onClick={onClose}
        aria-label={t('linkSafety.close')}
      >
        <X className="h-4 w-4" />
      </button>
      <LinkSafetyHeader title={t('linkSafety.title')} warning={t('linkSafety.warning')} />
      <p className="mb-4 break-all rounded-lg bg-muted/70 px-3 py-2 font-mono text-xs text-foreground">
        {url}
      </p>
      <LinkSafetyActions
        copyLabel={t('linkSafety.copy')}
        openLabel={t('linkSafety.open')}
        onCopy={() => void copyAndClose(url, onClose)}
        onOpen={() => {
          onConfirm()
          onClose()
        }}
      />
    </div>
  )
}

async function copyAndClose(url: string, onClose: () => void): Promise<void> {
  try {
    await navigator.clipboard.writeText(url)
  } catch {
    /* still dismiss — user can retry from the chat text */
  }
  onClose()
}
