import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { ResolvedIdentity } from '../../types'

// Supervisor-only screen (Task 10, DEANONYMIZE permission): resolves
// pseudonym<->matricola in both directions. The server is the sole authority
// on §6 role gating (this screen is only reachable via the supervisor nav,
// but a 403 from the backend is still handled gracefully); every resolution
// is audited server-side (identity_resolved), hence the standing warning.
function splitPseudonyms(raw: string): string[] {
  return raw
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export function Deanonymize() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()

  const [pseudonymsInput, setPseudonymsInput] = useState('')
  const [results, setResults] = useState<ResolvedIdentity[] | null>(null)
  const [resolveError, setResolveError] = useState('')
  const [busyResolve, setBusyResolve] = useState(false)

  const [matricola, setMatricola] = useState('')
  const [matricolaResult, setMatricolaResult] = useState<string | null>(null)
  const [matricolaNotFound, setMatricolaNotFound] = useState(false)
  const [matricolaError, setMatricolaError] = useState('')
  const [busyMatricola, setBusyMatricola] = useState(false)

  const pseudonymIds = splitPseudonyms(pseudonymsInput)

  async function submitPseudonyms(e: FormEvent) {
    e.preventDefault()
    if (pseudonymIds.length === 0) return
    setResolveError('')
    setResults(null)
    setBusyResolve(true)
    const r = await client.resolveIdentity(pseudonymIds)
    setBusyResolve(false)
    if (r.status === 'ok') setResults(r.results)
    else {
      const outcome = handleError(r.status)
      if (outcome !== 'handled') setResolveError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    }
  }

  async function submitMatricola(e: FormEvent) {
    e.preventDefault()
    const value = matricola.trim()
    if (!value) return
    setMatricolaError('')
    setMatricolaNotFound(false)
    setMatricolaResult(null)
    setBusyMatricola(true)
    const r = await client.resolveMatricola(value)
    setBusyMatricola(false)
    if (r.status === 'ok') setMatricolaResult(r.pseudonymId)
    else if (r.status === 'not-found') setMatricolaNotFound(true)
    else {
      const outcome = handleError(r.status)
      if (outcome !== 'handled') setMatricolaError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    }
  }

  return (
    <div className="deanonymize">
      <h1>{t('deanonymize.title')}</h1>
      <p className="warn" role="alert">{t('deanonymize.warning')}</p>

      <section>
        <h2>{t('deanonymize.byPseudonymTitle')}</h2>
        <form className="job-form" onSubmit={submitPseudonyms}>
          <label>
            {t('deanonymize.pseudonymsLabel')}
            <textarea value={pseudonymsInput} onChange={(e) => setPseudonymsInput(e.target.value)} />
          </label>
          {resolveError && <p className="error" role="alert">{resolveError}</p>}
          <button type="submit" disabled={busyResolve || pseudonymIds.length === 0}>{t('deanonymize.resolveButton')}</button>
        </form>

        {results && (
          results.length === 0 ? (
            <p>{t('deanonymize.noResults')}</p>
          ) : (
            <table>
              <thead>
                <tr><th>{t('deanonymize.colPseudonym')}</th><th>{t('deanonymize.colMatricola')}</th></tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.pseudonymId}>
                    <td>{r.pseudonymId}</td>
                    <td>{r.matricola}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </section>

      <section>
        <h2>{t('deanonymize.byMatricolaTitle')}</h2>
        <form className="job-form" onSubmit={submitMatricola}>
          <label>
            {t('deanonymize.matricolaLabel')}
            <input value={matricola} onChange={(e) => setMatricola(e.target.value)} />
          </label>
          {matricolaError && <p className="error" role="alert">{matricolaError}</p>}
          <button type="submit" disabled={busyMatricola || !matricola.trim()}>{t('deanonymize.findButton')}</button>
        </form>

        {matricolaNotFound && <p>{t('deanonymize.matricolaNotFound')}</p>}
        {matricolaResult && <p>{t('deanonymize.matricolaResult', { pseudonym: matricolaResult })}</p>}
      </section>
    </div>
  )
}
