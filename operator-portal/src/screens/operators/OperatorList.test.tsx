import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, ADMIN, OPERATORS } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { OperatorList } from './OperatorList'

afterEach(() => sessionStorage.clear())

function admin(overrides = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: ADMIN }, operators: { status: 'ok', operators: OPERATORS }, ...overrides })
}

test('lists operators with role, status, and per-status action', async () => {
  setToken('tok')
  renderWithProviders(<OperatorList />, { client: admin(), route: '/operators' })
  expect(await screen.findByText('Maria Rossi')).toBeInTheDocument()
  // active operator → Disabilita; disabled one → Riabilita
  expect(screen.getAllByRole('button', { name: 'Disabilita' }).length).toBeGreaterThan(0)
  expect(screen.getByRole('button', { name: 'Riabilita' })).toBeInTheDocument()
  // must_change badge present for g.bianchi
  expect(screen.getByText('Deve cambiare password')).toBeInTheDocument()
})

test('create flow: form sends the 3 fields, opens the temp-password modal, reloads', async () => {
  setToken('tok')
  const client = admin()
  renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await userEvent.click(screen.getByRole('button', { name: /Nuovo operatore/ }))
  await userEvent.type(screen.getByLabelText('Nome utente'), 'n.neri')
  await userEvent.type(screen.getByLabelText('Nome visualizzato'), 'Nadia Neri')
  await userEvent.selectOptions(screen.getByLabelText('Ruolo'), 'operator')
  await userEvent.click(screen.getByRole('button', { name: 'Crea operatore' }))
  expect(client.createdOperators[0]).toEqual({ username: 'n.neri', display_name: 'Nadia Neri', role: 'operator' })
  expect(await screen.findByText('7Kq9-mZ2t-Rf4x')).toBeInTheDocument() // modal
  await userEvent.click(screen.getByRole('button', { name: 'Ho copiato, chiudi' }))
  expect(screen.queryByText('7Kq9-mZ2t-Rf4x')).not.toBeInTheDocument() // cleared on close
  await waitFor(() => expect(client.calls.lops).toBe(2)) // reloaded
})

test('disable asks for confirmation; cancel does NOT call the client', async () => {
  setToken('tok')
  const client = admin()
  renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await userEvent.click(screen.getAllByRole('button', { name: 'Disabilita' })[0])
  expect(screen.getByText(/Disabilitare l’operatore «m.rossi»/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Annulla' }))
  expect(client.calls.opdisable).toBe(0)
})

test('disable confirmed calls disableOperator(id) and reloads', async () => {
  setToken('tok')
  const client = admin()
  renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await userEvent.click(screen.getAllByRole('button', { name: 'Disabilita' })[0])
  await userEvent.click(screen.getByRole('button', { name: 'Conferma' }))
  await waitFor(() => expect(client.disabledIds).toEqual([1]))
  await waitFor(() => expect(client.calls.lops).toBe(2))
})

test('reset confirmed opens the modal with the new temp-password', async () => {
  setToken('tok')
  const client = admin()
  renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await userEvent.click(screen.getAllByRole('button', { name: 'Reset password' })[0])
  await userEvent.click(screen.getByRole('button', { name: 'Conferma' }))
  expect(await screen.findByText('NEW-pw-123')).toBeInTheDocument()
  expect(client.resetIds).toEqual([1])
})

test('auto-lockout: the logged-in admin cannot disable/reset their own row', async () => {
  setToken('tok')
  // ADMIN.id = 9; include the admin in the list
  const withSelf = [...OPERATORS, ADMIN]
  renderWithProviders(<OperatorList />, { client: admin({ operators: { status: 'ok', operators: withSelf } }), route: '/operators' })
  // ADMIN.display_name and t('shell.role.admin') both render as "Amministratore" in
  // this row, so two elements match; either one's <tr> is the same (only) admin row.
  await screen.findAllByText('Amministratore')
  const row = screen.getAllByText('Amministratore')[0].closest('tr') as HTMLElement
  const { getByRole } = within(row)
  expect(getByRole('button', { name: 'Disabilita' })).toBeDisabled()
  expect(getByRole('button', { name: 'Reset password' })).toBeDisabled()
})

test('403 on mount shows the error, not a stuck loading spinner', async () => {
  setToken('tok')
  renderWithProviders(<OperatorList />, { client: admin({ operators: { status: 'forbidden' } }), route: '/operators' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})
