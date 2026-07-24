import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from './BigButton'

export function ConfirmCorrect({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  const { t } = useTranslation()
  const [correcting, setCorrecting] = useState(false)
  const [value, setValue] = useState('')
  const trimmed = value.trim()
  return (
    <div>
      <p className="prompt-text">{text}</p>
      {!correcting ? (
        <>
          <BigButton variant="confirm" onClick={() => onSubmit(t('confirm.yes'))}>
            {t('confirm.yes')}
          </BigButton>
          <BigButton variant="secondary" onClick={() => setCorrecting(true)}>
            {t('confirm.no')}
          </BigButton>
        </>
      ) : (
        <>
          <textarea
            aria-label={t('confirm.correctPlaceholder')}
            placeholder={t('confirm.correctPlaceholder')}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <BigButton variant="confirm" disabled={!trimmed} onClick={() => onSubmit(trimmed)}>
            {t('confirm.send')}
          </BigButton>
        </>
      )}
    </div>
  )
}
