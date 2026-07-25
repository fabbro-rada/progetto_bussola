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

test('admin sees admin sections', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } }),
  })
  await waitFor(() => expect(screen.getByText('Gestione utenze')).toBeInTheDocument())
  expect(screen.queryByText('Richieste di lavoro')).not.toBeInTheDocument()
})
