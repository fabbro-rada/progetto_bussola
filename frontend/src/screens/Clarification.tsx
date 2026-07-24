import { ConfirmCorrect } from '../components/ConfirmCorrect'

export function Clarification({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  return <ConfirmCorrect text={text} onSubmit={onSubmit} />
}
