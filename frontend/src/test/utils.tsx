import { render, type RenderResult } from '@testing-library/react'
import { type ReactElement } from 'react'
import { I18nextProvider } from 'react-i18next'
import i18n from '../i18n'
import { TextSizeProvider } from '../a11y/TextSize'

export function renderWithProviders(ui: ReactElement): RenderResult {
  return render(
    <I18nextProvider i18n={i18n}>
      <TextSizeProvider>{ui}</TextSizeProvider>
    </I18nextProvider>,
  )
}
