import { render, type RenderResult } from '@testing-library/react'
import { type ReactElement } from 'react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import i18n from '../i18n'
import { AuthProvider } from '../auth/AuthContext'
import { makeFakeClient } from './fakeClient'
import type { OperatorClient } from '../types'

export function renderWithProviders(
  ui: ReactElement,
  opts: { client?: OperatorClient; route?: string } = {},
): RenderResult {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[opts.route ?? '/']}>
        <AuthProvider client={opts.client ?? makeFakeClient({})}>{ui}</AuthProvider>
      </MemoryRouter>
    </I18nextProvider>,
  )
}
