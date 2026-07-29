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

test('admin sees «Gestione utenze» and «Configurazione» as real links', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Gestione utenze/ })).toHaveAttribute('href', '/operators')
  expect(await screen.findByRole('link', { name: /Configurazione/ })).toHaveAttribute('href', '/config')
})

test('the built sections render real links; Export is built too', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, { client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } }) })
  expect(await screen.findByRole('link', { name: /Richieste di lavoro/ })).toHaveAttribute('href', '/job-requests')
  expect(await screen.findByRole('link', { name: /Profili/ })).toHaveAttribute('href', '/profiles')
  expect(await screen.findByRole('link', { name: /Export/ })).toHaveAttribute('href', '/export')
})

test('supervisor sees «Metriche» and «Attività operatori» as real links', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Metriche/ })).toHaveAttribute('href', '/metrics')
  expect(await screen.findByRole('link', { name: /Attività operatori/ })).toHaveAttribute('href', '/activity')
})

test('supervisor sees «Report» as a real link', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, { client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } }) })
  expect(await screen.findByRole('link', { name: /Report/ })).toHaveAttribute('href', '/report')
})

test('supervisor sees «Approvazioni export» as a real link', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, { client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } }) })
  expect(await screen.findByRole('link', { name: /Approvazioni export/ })).toHaveAttribute('href', '/export-approvals')
})

test('auditor sees «Log di audit» as a real link', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'auditor' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Log di audit/ })).toHaveAttribute('href', '/audit')
})
