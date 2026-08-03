import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { JobRequest, MatchResult } from '../../types'
import { MatchResults } from './MatchResults'

export function JobRequestDetail() {
  const { t } = useTranslation()
  const { id } = useParams()
  const jobId = Number(id)
  const { client } = useAuth()
  const handleError = useApiError()
  const [job, setJob] = useState<JobRequest | null>(null)
  const [results, setResults] = useState<MatchResult[] | null>(null)
  const [error, setError] = useState('')
  const [matching, setMatching] = useState(false)
  const mountedRef = useRef(true)
  // Reset on (re)mount: React 18 StrictMode mounts → unmounts → remounts in
  // dev, so a cleanup-only effect would fire once and leave mountedRef stuck
  // false — runMatch would then bail after the 200 and never clear the
  // "calcolando…" state or render results. Setting it true here keeps it honest.
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    let active = true
    void client.getJobRequest(jobId).then((r) => {
      if (!active) return
      if (r.status === 'ok') setJob(r.job)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') setError(t(outcome === 'not-found' ? 'errors.notFound' : outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    })
    return () => { active = false }
  }, [client, handleError, jobId, t])

  async function runMatch() {
    setError('')
    setMatching(true)
    const r = await client.runMatch(jobId)
    if (!mountedRef.current) return
    setMatching(false)
    if (r.status === 'ok') setResults(r.results)
    else {
      const outcome = handleError(r.status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    }
  }

  if (error) return <p className="error" role="alert">{error}</p>
  if (job === null) return <p>{t('common.loading')}</p>

  return (
    <div className="job-detail">
      <p><Link to="/job-requests">← {t('detail.back')}</Link></p>
      <h1>{job.title}</h1>
      <p>{job.sector}</p>
      <h2>{t('detail.requirements')}</h2>
      <ul>
        {job.required_skills.map((s) => <li key={s}>{s}</li>)}
        {job.required_languages.map((l) => <li key={l.language}>{l.language} — {t(`jobForm.level_${l.min_level}`)}</li>)}
      </ul>
      <p>{t('jobForm.availability')}: {job.required_availability ? t(`jobForm.availability_${job.required_availability}`) : t('jobForm.availabilityNone')}</p>
      <p>{t('jobForm.nightShifts')}: {job.involves_night_shifts ? t('common.yes') : t('common.no')}</p>
      {job.training_prerequisites.length > 0 && (
        <>
          <h2>{t('jobForm.prerequisites')}</h2>
          <ul>{job.training_prerequisites.map((p) => <li key={p}>{p}</li>)}</ul>
        </>
      )}
      <button type="button" onClick={() => void runMatch()} disabled={matching}>{t('detail.runMatch')}</button>
      {matching && <p role="status">{t('detail.calculating')}</p>}
      {results !== null && <MatchResults results={results} />}
    </div>
  )
}
