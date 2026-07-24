import { ConfirmCorrect } from '../components/ConfirmCorrect'

export function Summary({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  return <ConfirmCorrect text={text} onSubmit={onSubmit} />
}
