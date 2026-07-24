import { AnswerPrompt } from '../components/AnswerPrompt'

export function Question({
  text,
  onSubmit,
  busy,
}: {
  text: string
  onSubmit: (answer: string) => void
  busy?: boolean
}) {
  return <AnswerPrompt text={text} onSubmit={onSubmit} busy={busy} />
}
