import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from './BigButton'

export function AnswerPrompt({
  text,
  onSubmit,
  banner,
}: {
  text: string
  onSubmit: (answer: string) => void
  banner?: string
}) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const trimmed = value.trim()
  return (
    <div>
      {banner && <div className="banner-warn">{banner}</div>}
      <p className="prompt-text">{text}</p>
      <textarea
        aria-label={t('prompt.placeholder')}
        placeholder={t('prompt.placeholder')}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <BigButton
        variant="confirm"
        disabled={!trimmed}
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
