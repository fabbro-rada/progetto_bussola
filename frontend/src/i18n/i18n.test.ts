import { expect, test } from 'vitest'
import i18n, { applyLanguage } from './index'
import { dirFor, LANGUAGES } from './languages'
import { it } from './locales/it'
import { en } from './locales/en'
import { fr } from './locales/fr'
import { es } from './locales/es'
import { ar } from './locales/ar'

test('all five languages are present with the right direction', () => {
  expect(LANGUAGES.map((l) => l.code)).toEqual(['it', 'en', 'fr', 'es', 'ar'])
  expect(dirFor('ar')).toBe('rtl')
  expect(dirFor('it')).toBe('ltr')
  expect(dirFor('unknown')).toBe('ltr')
})

test('every catalog has exactly the same keys as the Italian catalog', () => {
  const keysOf = (o: object, p = ''): string[] =>
    Object.entries(o).flatMap(([k, v]) =>
      typeof v === 'object' && v !== null ? keysOf(v, `${p}${k}.`) : [`${p}${k}`],
    )
  const itKeys = keysOf(it).sort()
  for (const cat of [en, fr, es, ar]) expect(keysOf(cat).sort()).toEqual(itKeys)
})

test('applyLanguage switches strings and sets document direction', () => {
  applyLanguage('it')
  expect(i18n.t('stop.label')).toBe('Ferma')
  expect(document.documentElement.dir).toBe('ltr')

  applyLanguage('ar')
  expect(i18n.t('stop.label')).toBe('إيقاف')
  expect(document.documentElement.dir).toBe('rtl')
  expect(document.documentElement.lang).toBe('ar')

  applyLanguage('en')
  expect(i18n.t('stop.label')).toBe('Stop')
})
