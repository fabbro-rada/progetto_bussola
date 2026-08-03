import { useTranslation } from 'react-i18next'
import { AnswerPrompt } from '../components/AnswerPrompt'

export function Refusal({
  question,
  onSubmit,
  busy,
}: {
  // The original question the person was answering, re-shown under the refusal
  // banner so they know what to reply to (the reply goes to the same section).
  question: string
  onSubmit: (answer: string) => void
  busy?: boolean
}) {
  const { t } = useTranslation()
  return <AnswerPrompt text={question} onSubmit={onSubmit} banner={t('refusal.banner')} busy={busy} />
}
