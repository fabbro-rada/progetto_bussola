import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from './BigButton'
import { VoiceBar } from './VoiceBar'

export function AnswerPrompt({
  text,
  onSubmit,
  banner,
  busy,
}: {
  text: string
  onSubmit: (answer: string) => void
  banner?: string
  busy?: boolean
}) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const [voiceBusy, setVoiceBusy] = useState(false)
  const trimmed = value.trim()
  return (
    <div>
      {banner && <div className="banner-warn">{banner}</div>}
      <p className="prompt-text">{text}</p>
      <VoiceBar text={text} canDictate onDictated={setValue} onBusyChange={setVoiceBusy} />
      <textarea
        aria-label={t('prompt.placeholder')}
        placeholder={t('prompt.placeholder')}
        value={value}
        disabled={voiceBusy}
        onChange={(e) => setValue(e.target.value)}
      />
      <BigButton
        variant="confirm"
        disabled={!trimmed || busy || voiceBusy}
        onClick={() => {
          onSubmit(trimmed)
          setValue('')
        }}
      >
        {t('prompt.next')}
      </BigButton>
    </div>
  )
}
