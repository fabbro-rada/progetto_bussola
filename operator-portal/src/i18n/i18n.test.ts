import { expect, test } from 'vitest'
import i18n from './index'

test('italian catalog resolves core auth/shell keys', async () => {
  await i18n.changeLanguage('it')
  expect(i18n.t('login.submit')).toBe('Entra')
  expect(i18n.t('shell.logout')).toBe('Esci')
  expect(i18n.t('errors.sessionExpired')).toBe('Sessione scaduta. Accedi di nuovo.')
})
