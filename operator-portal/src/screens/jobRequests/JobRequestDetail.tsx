import { useEffect, useState } from 'react'
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
      <button type="button" onClick={() => void runMatch()} disabled={matching}>{t('detail.runMatch')}</button>
      {matching && <p role="status">{t('detail.calculating')}</p>}
      {results !== null && <MatchResults results={results} />}
    </div>
  )
}
