import type { KioskClient, StartResult, Step, SubmitResult } from '../types'

const BASE = import.meta.env.VITE_API_BASE ?? ''
const TOKEN = import.meta.env.VITE_KIOSK_TOKEN ?? ''

function headers(): Record<string, string> {
  return { 'Content-Type': 'application/json', 'X-Kiosk-Token': TOKEN }
}

async function startInterview(language: string): Promise<StartResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/kiosk/interview/start`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ language }),
    })
  } catch {
    return { status: 'unavailable' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (!res.ok) return { status: 'unavailable' }
  const data = (await res.json()) as { session_token: string; step: Step }
  return { status: 'ok', sessionToken: data.session_token, step: data.step }
}

async function submitAnswer(sessionToken: string, answer: string): Promise<SubmitResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/kiosk/interview/submit`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ session_token: sessionToken, answer }),
    })
  } catch {
    return { status: 'unavailable' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 404) return { status: 'session-expired' }
  if (!res.ok) return { status: 'unavailable' }
  const data = (await res.json()) as { step: Step }
  return { status: 'ok', step: data.step }
}

export const kioskClient: KioskClient = { startInterview, submitAnswer }
