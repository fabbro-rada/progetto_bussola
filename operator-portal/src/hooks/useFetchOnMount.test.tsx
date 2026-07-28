import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { setToken } from '../auth/session'
import { useAuth } from '../auth/AuthContext'
import { useFetchOnMount } from './useFetchOnMount'
import { useCallback } from 'react'

function Probe() {
  const { client } = useAuth()
  const fetcher = useCallback(() => client.getMetrics(), [client])
  const { data, error } = useFetchOnMount(fetcher, (r) => r.metrics)
  if (error) return <p>ERR:{error}</p>
  if (data === null) return <p>LOADING</p>
  return <p>OK:{data.total_profiles}</p>
}

function harness() {
  return (
    <Routes>
      <Route path="/x" element={<Probe />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

afterEach(() => sessionStorage.clear())

test('ok → exposes the selected data', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, metrics: { status: 'ok', metrics: { total_profiles: 7, completed_profiles: 0, average_completeness: 0, total_job_requests: 0, matching_runs: 0 } } })
  renderWithProviders(harness(), { client, route: '/x' })
  expect(await screen.findByText('OK:7')).toBeInTheDocument()
})

test('forbidden → error message, no stuck loading', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, metrics: { status: 'forbidden' } })
  renderWithProviders(harness(), { client, route: '/x' })
  expect(await screen.findByText('ERR:Non hai i permessi per questa azione.')).toBeInTheDocument()
})

test('unauthorized → redirect to login', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, metrics: { status: 'unauthorized' } })
  renderWithProviders(harness(), { client, route: '/x' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})
