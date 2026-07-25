import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { JobRequest } from '../../types'

export function JobRequestList() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<JobRequest[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void client.listJobRequests().then((r) => {
      if (!active) return
      if (r.status === 'ok') setJobs(r.jobs)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    })
    return () => {
      active = false
    }
  }, [client, handleError, t])

  if (error) return <p className="error" role="alert">{error}</p>
  if (jobs === null) return <p>{t('common.loading')}</p>

  return (
    <div className="job-list">
      <div className="section-head">
        <h1>{t('jobRequests.title')}</h1>
        <Link className="btn" to="/job-requests/new">{t('jobRequests.new')}</Link>
      </div>
      {jobs.length === 0 ? (
        <p>{t('jobRequests.empty')}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>{t('jobRequests.colTitle')}</th>
              <th>{t('jobRequests.colSector')}</th>
              <th>{t('jobRequests.colCreatedBy')}</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} onClick={() => navigate(`/job-requests/${j.id}`)} style={{ cursor: 'pointer' }}>
                <td><Link to={`/job-requests/${j.id}`}>{j.title}</Link></td>
                <td>{j.sector}</td>
                <td>{j.created_by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
