import { render, type RenderResult } from '@testing-library/react'
import { type ReactElement } from 'react'
import { I18nextProvider } from 'react-i18next'
import i18n from '../i18n'
import { TextSizeProvider } from '../a11y/TextSize'
import { VoiceProvider } from '../voice/VoiceContext'
import { noopVoiceClient } from './fakeClient'
import type { VoiceClient } from '../voice/voiceClient'

export function renderWithProviders(
  ui: ReactElement,
  opts: { voiceClient?: VoiceClient; language?: string } = {},
): RenderResult {
  return render(
    <I18nextProvider i18n={i18n}>
      <TextSizeProvider>
        <VoiceProvider language={opts.language ?? 'it'} client={opts.voiceClient ?? noopVoiceClient}>
          {ui}
        </VoiceProvider>
      </TextSizeProvider>
    </I18nextProvider>,
  )
}
