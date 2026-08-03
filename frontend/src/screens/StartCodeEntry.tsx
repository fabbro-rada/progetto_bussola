import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { VoiceBar } from '../components/VoiceBar'

// Start-code entry (re-identification, Task 8): the kiosk no longer self-starts
// anonymously. Right after LanguagePicker — where the person has ALREADY chosen
// the language — they key in the one-time start code an operator gave them.
// `onSubmit` hands the code up to the (unchanged) consent screen, the point
// where the person can still say no before anything is sent (§4 voluntariness).
//
// The language is NOT asked again here (unlike FollowupEntry, which is reached
// via a discreet link that bypasses LanguagePicker and so must offer its own
// language grid): it was picked one screen ago, already drives read-aloud via
// the VoiceProvider, and re-asking it left "Continua" disabled after the person
// had merely pasted the code (they had no reason to re-pick a language).
export function StartCodeEntry({ onSubmit }: { onSubmit: (code: string) => void }) {
  const { t } = useTranslation()
  const [code, setCode] = useState('')
  const trimmed = code.trim()
  const spoken = [t('startCode.title'), t('startCode.codeLabel')].join('. ')

  return (
    <div className="start-code-entry">
      <h1>{t('startCode.title')}</h1>
      <VoiceBar text={spoken} />
      <label htmlFor="start-code">{t('startCode.codeLabel')}</label>
      <input
        id="start-code"
        type="text"
        autoComplete="off"
        value={code}
        placeholder={t('startCode.codePlaceholder')}
        onChange={(e) => setCode(e.target.value)}
      />
      <BigButton variant="confirm" disabled={!trimmed} onClick={() => onSubmit(trimmed)}>
        {t('startCode.submit')}
      </BigButton>
    </div>
  )
}
