import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LANGUAGES } from '../i18n/languages'
import { applyLanguage } from '../i18n'
import { BigButton } from '../components/BigButton'
import { Notice } from '../components/Notice'
import { VoiceBar } from '../components/VoiceBar'

// Follow-up entry (Sottosistema 29, Task 6): a returning person keys in the
// language they want to continue in and the one-time code an operator gave
// them. Nothing is sent to the backend from this screen — `onSubmit` only
// hands the pair up to the follow-up consent/recap (§4 voluntariness), which
// is the point where the person can still say no before anything happens.
//
// The language must be chosen HERE (not assumed/locked to Italian): a
// follow-up token carries no language (a work profile has none, §5), and
// about half the pilot population is not Italian-speaking (§7.1). Tapping a
// tile applies it immediately so the rest of this screen — and everything
// after — reads in the person's language right away, exactly like the first
// LanguagePicker does for a first interview.
export function FollowupEntry({
  onSubmit,
  onLanguageChange,
  notice = false,
}: {
  onSubmit: (token: string, language: string) => void
  // Fix round 1 (§4): notifies the app-level state of the chosen language as
  // soon as it's picked — separate from `onSubmit` — so voice narration
  // (which reads the language from app state, not from this screen's local
  // state) targets the right language while still on THIS screen, not only
  // after the form is submitted.
  onLanguageChange: (language: string) => void
  // True when the person landed back here after a follow-up code that didn't
  // work: show a gentle recovery notice so they re-key or ask for a new code.
  notice?: boolean
}) {
  const { t } = useTranslation()
  const [language, setLanguage] = useState<string | null>(null)
  const [token, setToken] = useState('')
  const trimmed = token.trim()
  const spoken = [t('followupEntry.title'), t('followupEntry.tokenLabel')].join('. ')

  function selectLanguage(code: string) {
    setLanguage(code)
    applyLanguage(code)
    onLanguageChange(code)
  }

  return (
    <div className="followup-entry">
      <h1>{t('followupEntry.title')}</h1>
      {notice && <Notice tone="warn" text={t('followupEntry.retryNotice')} />}
      <div className="language-grid" role="group" aria-label={t('followupEntry.languageGroupLabel')}>
        {LANGUAGES.map((l) => (
          <button
            key={l.code}
            type="button"
            className="language-tile"
            aria-pressed={language === l.code}
            dir={l.dir}
            lang={l.code}
            onClick={() => selectLanguage(l.code)}
          >
            {l.name}
          </button>
        ))}
      </div>
      {/* Only once a language is chosen (§4): before that, there's no
          language to narrate in, same as the rest of this screen only
          becoming meaningful post-language-selection. */}
      {language && <VoiceBar text={spoken} />}
      <label htmlFor="followup-token">{t('followupEntry.tokenLabel')}</label>
      <input
        id="followup-token"
        type="text"
        autoComplete="off"
        value={token}
        placeholder={t('followupEntry.tokenPlaceholder')}
        onChange={(e) => setToken(e.target.value)}
      />
      <BigButton
        variant="confirm"
        disabled={!language || !trimmed}
        onClick={() => {
          if (language) onSubmit(trimmed, language)
        }}
      >
        {t('followupEntry.submit')}
      </BigButton>
    </div>
  )
}
