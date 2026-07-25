import { act, renderHook, screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { type ReactNode } from 'react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import i18n from '../i18n'
import { AuthProvider } from '../auth/AuthContext'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { setToken, getToken } from '../auth/session'
import { useApiError } from './useApiError'

afterEach(() => sessionStorage.clear())

function wrap(): ({ children }: { children: ReactNode }) => JSX.Element {
  return ({ children }) => (
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={['/x']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider client={makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })}>
          <Routes>
            <Route path="/x" element={<>{children}</>} />
            <Route path="/login" element={<div>LOGIN</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </I18nextProvider>
  )
}

test('unauthorized clears the token and is reported as handled', async () => {
  setToken('tok')
  const { result } = renderHook(() => useApiError(), { wrapper: wrap() })
  // Flush AuthProvider's mount-time me() resolution (token present → it fetches) before acting,
  // so that update — and the onUnauthorized/navigate updates triggered below — land inside
  // act() and test output stays pristine.
  await act(async () => {})
  let outcome: ReturnType<typeof result.current> | undefined
  act(() => {
    outcome = result.current('unauthorized')
  })
  expect(outcome).toBe('handled')
  expect(getToken()).toBeNull()
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})

test('forbidden/not-found/error are returned unchanged', () => {
  const { result } = renderHook(() => useApiError(), { wrapper: wrap() })
  expect(result.current('forbidden')).toBe('forbidden')
  expect(result.current('not-found')).toBe('not-found')
  expect(result.current('error')).toBe('error')
})
