import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { Metrics } from '../../types'

export function MetricsPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void client.getMetrics().then((r) => {
      if (!active) return
      if (r.status === 'ok') setMetrics(r.metrics)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    })
    return () => {
      active = false
    }
  }, [client, handleError, t])

  return (
    <div className="metrics">
      <h1>{t('metrics.title')}</h1>
      {error && <p className="error" role="alert">{error}</p>}
      {metrics === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        metrics && (
          <div className="metric-cards">
            <div className="metric-card"><span className="metric-value">{metrics.total_profiles}</span><span className="metric-label">{t('metrics.totalProfiles')}</span></div>
            <div className="metric-card"><span className="metric-value">{metrics.completed_profiles}</span><span className="metric-label">{t('metrics.completedProfiles')}</span></div>
            <div className="metric-card"><span className="metric-value">{Math.round(metrics.average_completeness * 100)}%</span><span className="metric-label">{t('metrics.averageCompleteness')}</span></div>
            <div className="metric-card"><span className="metric-value">{metrics.total_job_requests}</span><span className="metric-label">{t('metrics.totalJobRequests')}</span></div>
            <div className="metric-card"><span className="metric-value">{metrics.matching_runs}</span><span className="metric-label">{t('metrics.matchingRuns')}</span></div>
          </div>
        )
      )}
    </div>
  )
}
