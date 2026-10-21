import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { defaultNS, resources } from './resources'

void i18n.use(initReactI18next).init({
  resources,
  lng: 'en',
  fallbackLng: 'en',
  defaultNS,
  ns: ['common', 'assistant'],
  interpolation: { escapeValue: false },
})

syncHtmlLang('en')

/** Keep <html lang/dir> in sync for a future locale switcher. */
export function syncHtmlLang(locale: string, dir: 'ltr' | 'rtl' | 'auto' = 'ltr'): void {
  if (typeof document === 'undefined') return
  document.documentElement.lang = locale
  document.documentElement.dir = dir
}

export { defaultNS, resources }
export default i18n
