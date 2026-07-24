import { AnswerPrompt } from '../components/AnswerPrompt'

export function Question({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  return <AnswerPrompt text={text} onSubmit={onSubmit} />
}
