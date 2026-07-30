import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, PROFILE } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ProfileDetail } from './ProfileDetail'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/profiles/:pseudonym" element={<ProfileDetail />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

test('renders the work-only profile with per-skill evidence grade', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profile: { status: 'ok', profile: PROFILE } })
  renderWithProviders(harness(), { client, route: '/profiles/P-4F2A' })
  expect(await screen.findByText('P-4F2A')).toBeInTheDocument()
  expect(screen.getByText('Cucina')).toBeInTheDocument()
  expect(screen.getByText(/Certificata/)).toBeInTheDocument() // skill evidence grade
  expect(screen.getByText(/Dichiarata/)).toBeInTheDocument()
  expect(screen.getByText('Aiuto cuoco')).toBeInTheDocument() // experience
  expect(screen.getByText(/Niente turni notturni/)).toBeInTheDocument() // constraint label
  expect(screen.getByText(/Supporto linguistico/)).toBeInTheDocument() // operational note label
})

test('404 shows the not-found message', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profile: { status: 'not-found' } })
  renderWithProviders(harness(), { client, route: '/profiles/P-XXXX' })
  expect(await screen.findByText('Profilo non trovato.')).toBeInTheDocument()
})

test('«Nuovo follow-up» requests a token for this pseudonym and shows it once in a modal', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    profile: { status: 'ok', profile: PROFILE },
    createFollowup: { status: 'ok', token: 'FUP-9K2M-7QRT' },
  })
  renderWithProviders(harness(), { client, route: '/profiles/P-4F2A' })
  await screen.findByText('P-4F2A')
  await userEvent.click(screen.getByRole('button', { name: 'Nuovo follow-up' }))
  expect(await screen.findByRole('dialog')).toBeInTheDocument()
  expect(screen.getByText('FUP-9K2M-7QRT')).toBeInTheDocument()
  expect(client.followupPseudonyms).toEqual(['P-4F2A'])

  // shown once: closing the modal clears the token from view
  await userEvent.click(screen.getByRole('button', { name: 'Ho copiato, chiudi' }))
  expect(screen.queryByText('FUP-9K2M-7QRT')).not.toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('a forbidden follow-up request shows the forbidden message instead of a modal', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    profile: { status: 'ok', profile: PROFILE },
    createFollowup: { status: 'forbidden' },
  })
  renderWithProviders(harness(), { client, route: '/profiles/P-4F2A' })
  await screen.findByText('P-4F2A')
  await userEvent.click(screen.getByRole('button', { name: 'Nuovo follow-up' }))
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
