import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import { StartCodeModal } from './StartCodeModal'

// Operator "new interview" (provision) screen (Task 9): the operator enters a
// matricola and gets a one-time start_code to hand to the person, who uses it
// to begin their interview on a kiosk. Mirrors the follow-up minting flow in
// ProfileDetail — mutation, then a one-time-secret modal — with its own
// duplicate-matricola outcome ('conflict', 409) instead of a generic error.
export function NewInterview() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [matricola, setMatricola] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [startCode, setStartCode] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    const r = await client.provisionInterview(matricola)
    setBusy(false)
    if (r.status === 'ok') {
      setStartCode(r.startCode)
      setMatricola('')
    } else if (r.status === 'conflict') {
      setError(t('interviews.conflict'))
    } else {
      const outcome = handleError(r.status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    }
  }

  return (
    <div className="new-interview">
      <form className="job-form" onSubmit={submit}>
        <h1>{t('interviews.title')}</h1>
        <label>
          {t('interviews.matricola')}
          <input value={matricola} onChange={(e) => setMatricola(e.target.value)} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={busy || !matricola.trim()}>{t('interviews.submit')}</button>
      </form>

      {startCode && (
        <StartCodeModal code={startCode} subtitle={t('interviews.startCodeSubtitle')} onClose={() => setStartCode(null)} />
      )}
    </div>
  )
}
