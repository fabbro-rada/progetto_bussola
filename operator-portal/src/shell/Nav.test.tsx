import { screen, waitFor } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { setToken } from '../auth/session'
import { Nav } from './Nav'

afterEach(() => sessionStorage.clear())

test('operator sees operator sections, not admin ones', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } }),
  })
  await waitFor(() => expect(screen.getByText('Richieste di lavoro')).toBeInTheDocument())
  expect(screen.getByText('Profili')).toBeInTheDocument()
  expect(screen.queryByText('Gestione utenze')).not.toBeInTheDocument()
})

test('admin sees admin sections; «Gestione utenze» is a real link, Config stays disabled', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Gestione utenze/ })).toHaveAttribute('href', '/operators')
  expect(screen.queryByText('Richieste di lavoro')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Configurazione/ })).not.toBeInTheDocument()
})

test('the built sections render real links; others stay disabled', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, { client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } }) })
  expect(await screen.findByRole('link', { name: /Richieste di lavoro/ })).toHaveAttribute('href', '/job-requests')
  expect(await screen.findByRole('link', { name: /Profili/ })).toHaveAttribute('href', '/profiles')
  // 'Export' is not yet built → not a link
  expect(screen.queryByRole('link', { name: /Export/ })).not.toBeInTheDocument()
})
