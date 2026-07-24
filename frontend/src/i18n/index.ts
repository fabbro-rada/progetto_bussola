import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { dirFor } from './languages'
import { it } from './locales/it'
import { en } from './locales/en'
import { fr } from './locales/fr'
import { es } from './locales/es'
import { ar } from './locales/ar'

void i18n.use(initReactI18next).init({
  resources: {
    it: { translation: it },
    en: { translation: en },
    fr: { translation: fr },
    es: { translation: es },
    ar: { translation: ar },
  },
  lng: 'it',
  fallbackLng: 'it',
  interpolation: { escapeValue: false },
})

export function applyLanguage(code: string): void {
  void i18n.changeLanguage(code)
  const dir = dirFor(code)
  document.documentElement.dir = dir
  document.documentElement.lang = code
}

export default i18n
