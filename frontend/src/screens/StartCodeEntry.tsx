import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LANGUAGES } from '../i18n/languages'
import { applyLanguage } from '../i18n'
import { BigButton } from '../components/BigButton'
import { VoiceBar } from '../components/VoiceBar'

// Start-code entry (re-identification, Task 8): the kiosk no longer
// self-starts anonymously. The very first thing a NEW person does after
// LanguagePicker is key in the one-time start code an operator gave them;
// `onSubmit` only hands the pair up to the (unchanged) consent screen,
// which is the point where the person can still say no before anything is
// sent (§4 voluntariness) — mirrors FollowupEntry.tsx exactly.
//
// The language is asked again HERE (not just carried over from
// LanguagePicker): mirroring FollowupEntry means this screen gives the
// person one more chance to correct a mis-tap before the code they are
// about to enter is even sent, consistent with the "confirm/correct
// before commit" pattern used throughout the kiosk (§5). Tapping a tile
// applies it immediately so the rest of this screen — and everything
// after — reads in the person's language right away.
export function StartCodeEntry({
  onSubmit,
  onLanguageChange,
}: {
  onSubmit: (code: string, language: string) => void
  // Notifies the app-level state of the chosen language as soon as it's
  // picked — separate from `onSubmit` — so voice narration (which reads the
  // language from app state, not from this screen's local state) targets
  // the right language while still on THIS screen, not only after the form
  // is submitted.
  onLanguageChange: (language: string) => void
}) {
  const { t } = useTranslation()
  const [language, setLanguage] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const trimmed = code.trim()
  const spoken = [t('startCode.title'), t('startCode.codeLabel')].join('. ')

  function selectLanguage(code: string) {
    setLanguage(code)
    applyLanguage(code)
    onLanguageChange(code)
  }

  return (
    <div className="start-code-entry">
      <h1>{t('startCode.title')}</h1>
      <div className="language-grid" role="group" aria-label={t('startCode.languageGroupLabel')}>
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
      <label htmlFor="start-code">{t('startCode.codeLabel')}</label>
      <input
        id="start-code"
        type="text"
        autoComplete="off"
        value={code}
        placeholder={t('startCode.codePlaceholder')}
        onChange={(e) => setCode(e.target.value)}
      />
      <BigButton
        variant="confirm"
        disabled={!language || !trimmed}
        onClick={() => {
          if (language) onSubmit(trimmed, language)
        }}
      >
        {t('startCode.submit')}
      </BigButton>
    </div>
  )
}
