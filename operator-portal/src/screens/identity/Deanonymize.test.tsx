import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { Deanonymize } from './Deanonymize'

afterEach(() => sessionStorage.clear())

test('pasting pseudonyms and resolving shows the matricole in a table', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) },
    resolveIdentity: { status: 'ok', results: [{ pseudonymId: 'P-4F2A', matricola: 'MAT-100' }, { pseudonymId: 'P-9B1C', matricola: 'MAT-207' }] },
  })
  renderWithProviders(<Deanonymize />, { client })
  await userEvent.type(screen.getByLabelText('Pseudonimi (uno per riga o separati da virgola)'), 'P-4F2A, P-9B1C')
  await userEvent.click(screen.getByRole('button', { name: 'De-anonimizza' }))
  expect(await screen.findByText('MAT-100')).toBeInTheDocument()
  expect(screen.getByText('MAT-207')).toBeInTheDocument()
  expect(screen.getByText('P-4F2A')).toBeInTheDocument()
  expect(screen.getByText('P-9B1C')).toBeInTheDocument()
  expect(client.resolvedPseudonymBatches).toEqual([['P-4F2A', 'P-9B1C']])
})

test('a single matricola resolves to its pseudonym', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) },
    resolveMatricola: { status: 'ok', pseudonymId: 'P-4F2A' },
  })
  renderWithProviders(<Deanonymize />, { client })
  await userEvent.type(screen.getByLabelText('Matricola'), 'MAT-100')
  await userEvent.click(screen.getByRole('button', { name: 'Trova pseudonimo' }))
  expect(await screen.findByText(/P-4F2A/)).toBeInTheDocument()
  expect(client.resolvedMatriculas).toEqual(['MAT-100'])
})

test('an unknown matricola shows a not-found message', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) },
    resolveMatricola: { status: 'not-found' },
  })
  renderWithProviders(<Deanonymize />, { client })
  await userEvent.type(screen.getByLabelText('Matricola'), 'MAT-999')
  await userEvent.click(screen.getByRole('button', { name: 'Trova pseudonimo' }))
  expect(await screen.findByText(/non trovat[oa]/i)).toBeInTheDocument()
})

test('a forbidden result on pseudonym resolution shows the permissions message', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith({ role: 'operator' }) },
    resolveIdentity: { status: 'forbidden' },
  })
  renderWithProviders(<Deanonymize />, { client })
  await userEvent.type(screen.getByLabelText('Pseudonimi (uno per riga o separati da virgola)'), 'P-4F2A')
  await userEvent.click(screen.getByRole('button', { name: 'De-anonimizza' }))
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('MAT-100')).not.toBeInTheDocument()
})

test('the warning banner about tracked access is always shown', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  renderWithProviders(<Deanonymize />, { client })
  expect(await screen.findByText(/ogni accesso è tracciato/i)).toBeInTheDocument()
})
