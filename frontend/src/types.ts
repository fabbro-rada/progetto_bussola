export type StepKind =
  | 'question'
  | 'summary'
  | 'clarification'
  | 'refusal'
  | 'unavailable'
  | 'completed'
  | 'recap'

// Minimal view of the work profile shown at the recap (person's own data).
export interface WorkProfileView {
  pseudonym_id: string
  languages: { language: string; level: string }[]
  digital_literacy: string | null
  skills: { name: string; kind: string; evidence: string }[]
  experiences: { role: string; sector: string; duration_months: number }[]
  aspiration: { fields_of_interest: string[]; availability: string | null; constraints: string[] } | null
  desired_training: { topic: string }[]
  operational_notes: string[]
}

export interface Step {
  kind: StepKind
  text: string
  recap?: WorkProfileView
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

export type Screen =
  | 'language'
  | 'startCodeEntry'
  | 'consent'
  | 'followupEntry'
  | 'followupConsent'
  | StepKind
  | 'unauthorized'

export interface KioskClient {
  startInterview(startCode: string, language: string): Promise<StartResult>
  submitAnswer(sessionToken: string, answer: string): Promise<SubmitResult>
  startFollowup(token: string, language: string): Promise<StartResult>
}
