import { screen } from '@testing-library/react'
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
