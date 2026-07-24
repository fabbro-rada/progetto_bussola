export interface LanguageMeta {
  code: string
  name: string
  dir: 'ltr' | 'rtl'
}

// Each endonym is written in its own language/script (constant, not translated).
export const LANGUAGES: LanguageMeta[] = [
  { code: 'it', name: 'Italiano', dir: 'ltr' },
  { code: 'en', name: 'English', dir: 'ltr' },
  { code: 'fr', name: 'Français', dir: 'ltr' },
  { code: 'es', name: 'Español', dir: 'ltr' },
  { code: 'ar', name: 'العربية', dir: 'rtl' },
]

export function dirFor(code: string): 'ltr' | 'rtl' {
  return LANGUAGES.find((l) => l.code === code)?.dir ?? 'ltr'
}
