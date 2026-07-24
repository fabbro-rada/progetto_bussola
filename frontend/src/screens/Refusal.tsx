import { useTranslation } from 'react-i18next'
import { AnswerPrompt } from '../components/AnswerPrompt'

export function Refusal({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  const { t } = useTranslation()
  return <AnswerPrompt text={text} onSubmit={onSubmit} banner={t('refusal.banner')} />
}
