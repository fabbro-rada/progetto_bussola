import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Unauthorized } from './Unauthorized'
import i18n from '../i18n'

test('shows the station-not-authorized message', async () => {
  await i18n.changeLanguage('it')
  renderWithProviders(<Unauthorized />)
  expect(screen.getByText(/Questa postazione non è autorizzata/)).toBeInTheDocument()
})
