import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, EXPORT_REQUEST } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ExportRequests } from './ExportRequests'

afterEach(() => sessionStorage.clear())

function harness(saveBlob = vi.fn()) {
  return (
    <Routes>
      <Route path="/export" element={<ExportRequests saveBlob={saveBlob} />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function op(overrides = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, ...overrides })
}

test('lists own requests with a readable scope and status', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: op(), route: '/export' })
  expect(await screen.findByText('cucina')).toBeInTheDocument() // filterSummary of {skill_query:'cucina'}
  expect(screen.getByText('In attesa')).toBeInTheDocument()
})

test('the new-request form sends the set filters + reason and reloads', async () => {
  setToken('tok')
  const client = op()
  renderWithProviders(harness(), { client, route: '/export' })
  await screen.findByText('cucina')
  await userEvent.click(screen.getByRole('button', { name: /Nuova richiesta/ }))
  await userEvent.type(screen.getByLabelText('Competenza'), 'muratura')
  await userEvent.type(screen.getByLabelText('Motivo / destinatario'), 'Azienda Y')
  await userEvent.click(screen.getByRole('button', { name: 'Invia richiesta' }))
  expect(client.createdExports[0]).toEqual({ filters: { skill_query: 'muratura' }, reason: 'Azienda Y' })
  await waitFor(() => expect(client.calls.expList).toBe(2)) // reloaded
})

test('reason is required: submit is disabled until it is filled', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: op(), route: '/export' })
  await screen.findByText('cucina')
  await userEvent.click(screen.getByRole('button', { name: /Nuova richiesta/ }))
  expect(screen.getByRole('button', { name: 'Invia richiesta' })).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Motivo / destinatario'), 'x')
  expect(screen.getByRole('button', { name: 'Invia richiesta' })).toBeEnabled()
})

test('Download is shown only for approved requests and triggers the file save', async () => {
  setToken('tok')
  const approved = { ...EXPORT_REQUEST, id: 7, status: 'approved' as const }
  const saveBlob = vi.fn()
  const client = op({ exports: { status: 'ok', requests: [approved] } })
  renderWithProviders(harness(saveBlob), { client, route: '/export' })
  const btn = await screen.findByRole('button', { name: 'Scarica' })
  await userEvent.click(btn)
  await waitFor(() => expect(client.downloadedIds).toEqual([7]))
  await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'export-7.json'))
})

test('a pending request has no Download button', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: op(), route: '/export' }) // default EXPORT_REQUEST is pending
  await screen.findByText('cucina')
  expect(screen.queryByRole('button', { name: 'Scarica' })).not.toBeInTheDocument()
})

test('403 on mount shows the error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: op({ exports: { status: 'forbidden' } }), route: '/export' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})
