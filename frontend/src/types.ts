export type StepKind =
  | 'question'
  | 'summary'
  | 'clarification'
  | 'refusal'
  | 'unavailable'
  | 'completed'

export interface Step {
  kind: StepKind
  text: string
}

export type StartResult =
  | { status: 'ok'; sessionToken: string; step: Step }
  | { status: 'unauthorized' }
  | { status: 'unavailable' }

export type SubmitResult =
  | { status: 'ok'; step: Step }
  | { status: 'session-expired' }
  | { status: 'unauthorized' }
  | { status: 'unavailable' }

export type Screen = 'language' | 'consent' | 'followupEntry' | 'followupConsent' | StepKind | 'unauthorized'

export interface KioskClient {
  startInterview(language: string): Promise<StartResult>
  submitAnswer(sessionToken: string, answer: string): Promise<SubmitResult>
  startFollowup(token: string, language: string): Promise<StartResult>
}
