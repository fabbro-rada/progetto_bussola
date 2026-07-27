import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, EXPORT_REQUEST } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ExportApprovals } from './ExportApprovals'

afterEach(() => sessionStorage.clear())

function sup(overrides = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, ...overrides })
}

test('shows the pending queue with requester, readable scope, and reason', async () => {
  setToken('tok')
  renderWithProviders(<ExportApprovals />, { client: sup(), route: '/export-approvals' })
  expect(await screen.findByText('m.rossi')).toBeInTheDocument()
  expect(screen.getByText('cucina')).toBeInTheDocument()
  expect(screen.getByText('Azienda X')).toBeInTheDocument()
  expect(screen.getByText('Motivo')).toBeInTheDocument()
})

test('empty filters render as «Tutti i profili»', async () => {
  setToken('tok')
  const allProfiles = { ...EXPORT_REQUEST, id: 9, filters: {} }
  renderWithProviders(<ExportApprovals />, { client: sup({ pending: { status: 'ok', requests: [allProfiles] } }), route: '/export-approvals' })
  expect(await screen.findByText('Tutti i profili')).toBeInTheDocument()
})

test('approve asks for confirmation then calls approveExport and reloads', async () => {
  setToken('tok')
  const client = sup()
  renderWithProviders(<ExportApprovals />, { client, route: '/export-approvals' })
  await screen.findByText('m.rossi')
  await userEvent.click(screen.getByRole('button', { name: 'Approva' }))
  expect(screen.getByText(/Ambito: cucina/)).toBeInTheDocument()
  expect(screen.getByText(/Motivo: Azienda X/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Conferma' }))
  await waitFor(() => expect(client.approvedIds).toEqual([1]))
  await waitFor(() => expect(client.calls.expPending).toBe(2))
})

test('deny requires a reason and sends it', async () => {
  setToken('tok')
  const client = sup()
  renderWithProviders(<ExportApprovals />, { client, route: '/export-approvals' })
  await screen.findByText('m.rossi')
  await userEvent.click(screen.getByRole('button', { name: 'Nega' }))
  const confirm = screen.getByRole('button', { name: 'Conferma rifiuto' })
  expect(confirm).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Motivo del rifiuto'), 'fuori scopo')
  await userEvent.click(confirm)
  await waitFor(() => expect(client.deniedExports).toEqual([{ id: 1, reason: 'fuori scopo' }]))
})

test('403 on mount shows the error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(<ExportApprovals />, { client: sup({ pending: { status: 'forbidden' } }), route: '/export-approvals' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})
