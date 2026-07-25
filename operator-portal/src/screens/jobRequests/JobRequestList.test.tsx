import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, JOB } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { JobRequestList } from './JobRequestList'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/job-requests" element={<JobRequestList />} />
      <Route path="/job-requests/new" element={<div>NEW</div>} />
      <Route path="/job-requests/:id" element={<div>DETAIL</div>} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

test('renders the job requests with a link to each detail and to new', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, jobs: { status: 'ok', jobs: [JOB] } })
  renderWithProviders(harness(), { client, route: '/job-requests' })
  expect(await screen.findByText('Aiuto cuoco')).toBeInTheDocument()
  expect(screen.getByText('Ristorazione')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Aiuto cuoco' })).toHaveAttribute('href', '/job-requests/7')
  expect(screen.getByRole('link', { name: 'Nuova richiesta' })).toHaveAttribute('href', '/job-requests/new')
})

test('empty state when there are no requests', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, jobs: { status: 'ok', jobs: [] } })
  renderWithProviders(harness(), { client, route: '/job-requests' })
  expect(await screen.findByText('Nessuna richiesta di lavoro.')).toBeInTheDocument()
})

test('401 while listing redirects to login', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, jobs: { status: 'unauthorized' } })
  renderWithProviders(harness(), { client, route: '/job-requests' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})
