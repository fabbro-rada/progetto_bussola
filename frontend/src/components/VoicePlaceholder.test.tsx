import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { VoicePlaceholder } from './VoicePlaceholder'
import i18n from '../i18n'

test('is present but inert (aria-hidden, no interactive control)', async () => {
  await i18n.changeLanguage('it')
  const { container } = renderWithProviders(<VoicePlaceholder />)
  const el = container.querySelector('.voice-placeholder')
  expect(el).toBeTruthy()
  expect(el).toHaveAttribute('aria-hidden', 'true')
})
