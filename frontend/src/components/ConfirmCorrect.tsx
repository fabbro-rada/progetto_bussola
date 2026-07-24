import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from './BigButton'
import { VoiceBar } from './VoiceBar'

export function ConfirmCorrect({
  text,
  onSubmit,
  busy,
}: {
  text: string
  onSubmit: (answer: string) => void
  busy?: boolean
}) {
  const { t } = useTranslation()
  const [correcting, setCorrecting] = useState(false)
  const [value, setValue] = useState('')
  const trimmed = value.trim()
  return (
    <div>
      <p className="prompt-text">{text}</p>
      {!correcting ? (
        <>
          <VoiceBar text={text} />
          <BigButton variant="confirm" disabled={busy} onClick={() => onSubmit(t('confirm.yes'))}>
            {t('confirm.yes')}
          </BigButton>
          <BigButton variant="secondary" onClick={() => setCorrecting(true)}>
            {t('confirm.no')}
          </BigButton>
        </>
      ) : (
        <>
          <VoiceBar text={text} canDictate onDictated={setValue} />
          <textarea
            aria-label={t('confirm.correctPlaceholder')}
            placeholder={t('confirm.correctPlaceholder')}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <BigButton variant="confirm" disabled={!trimmed || busy} onClick={() => onSubmit(trimmed)}>
            {t('confirm.send')}
          </BigButton>
        </>
      )}
    </div>
  )
}
