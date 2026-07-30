import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LANGUAGES } from '../i18n/languages'
import { applyLanguage } from '../i18n'
import { BigButton } from '../components/BigButton'

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
export function FollowupEntry({ onSubmit }: { onSubmit: (token: string, language: string) => void }) {
  const { t } = useTranslation()
  const [language, setLanguage] = useState<string | null>(null)
  const [token, setToken] = useState('')
  const trimmed = token.trim()

  function selectLanguage(code: string) {
    setLanguage(code)
    applyLanguage(code)
  }

  return (
    <div className="followup-entry">
      <h1>{t('followupEntry.title')}</h1>
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
