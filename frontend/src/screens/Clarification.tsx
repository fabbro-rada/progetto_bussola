import { AnswerPrompt } from '../components/AnswerPrompt'

// A clarification is an OPEN question ("what exactly did you do as X?"),
// NOT a yes/no confirmation — so it takes a free text/voice answer, exactly
// like a section Question. (The Sì/No confirm UI belongs to the Summary and
// the final Recap, where the person confirms or corrects what was understood.)
export function Clarification({
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
