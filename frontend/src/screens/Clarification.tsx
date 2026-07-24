import { ConfirmCorrect } from '../components/ConfirmCorrect'

export function Clarification({
  text,
  onSubmit,
  busy,
}: {
  text: string
  onSubmit: (answer: string) => void
  busy?: boolean
}) {
  return <ConfirmCorrect text={text} onSubmit={onSubmit} busy={busy} />
}
