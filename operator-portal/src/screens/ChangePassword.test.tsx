import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient } from '../test/fakeClient'
import { ChangePassword } from './ChangePassword'

afterEach(() => sessionStorage.clear())

function Harness() {
  return (
    <Routes>
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/" element={<div>HOME</div>} />
    </Routes>
  )
}

test('successful change navigates home', async () => {
  const client = makeFakeClient({ change: { status: 'ok' } })
  renderWithProviders(<Harness />, { client, route: '/change-password' })
  await userEvent.type(screen.getByLabelText('Password attuale'), 'oldpw')
  await userEvent.type(screen.getByLabelText('Nuova password'), 'newpassword')
  await userEvent.click(screen.getByRole('button', { name: 'Salva la nuova password' }))
  await waitFor(() => expect(screen.getByText('HOME')).toBeInTheDocument())
})

test('error shows a message and stays on the form', async () => {
  const client = makeFakeClient({ change: { status: 'error' } })
  renderWithProviders(<Harness />, { client, route: '/change-password' })
  await userEvent.type(screen.getByLabelText('Password attuale'), 'oldpw')
  await userEvent.type(screen.getByLabelText('Nuova password'), 'x')
  await userEvent.click(screen.getByRole('button', { name: 'Salva la nuova password' }))
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})
