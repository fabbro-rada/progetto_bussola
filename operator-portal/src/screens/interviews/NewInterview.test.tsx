import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { NewInterview } from './NewInterview'

afterEach(() => sessionStorage.clear())

test('entering a matricola and submitting shows the start code once in a modal', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    provisionInterview: { status: 'ok', startCode: 'START-7Q2K-9MRT' },
  })
  renderWithProviders(<NewInterview />, { client })
  await userEvent.type(screen.getByLabelText('Matricola'), 'MAT-100')
  await userEvent.click(screen.getByRole('button', { name: 'Genera codice' }))
  expect(await screen.findByRole('dialog')).toBeInTheDocument()
  expect(screen.getByText('START-7Q2K-9MRT')).toBeInTheDocument()
  expect(client.provisionedMatriculas).toEqual(['MAT-100'])

  // shown once: closing the modal clears the code from view
  await userEvent.click(screen.getByRole('button', { name: 'Ho copiato, chiudi' }))
  expect(screen.queryByText('START-7Q2K-9MRT')).not.toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('a duplicate matricola shows the conflict message instead of a modal', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    provisionInterview: { status: 'conflict' },
  })
  renderWithProviders(<NewInterview />, { client })
  await userEvent.type(screen.getByLabelText('Matricola'), 'MAT-DUP')
  await userEvent.click(screen.getByRole('button', { name: 'Genera codice' }))
  expect(await screen.findByText(/Esiste già un profilo per questa matricola/)).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('a forbidden provision shows the forbidden message instead of a modal', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    provisionInterview: { status: 'forbidden' },
  })
  renderWithProviders(<NewInterview />, { client })
  await userEvent.type(screen.getByLabelText('Matricola'), 'MAT-100')
  await userEvent.click(screen.getByRole('button', { name: 'Genera codice' }))
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
