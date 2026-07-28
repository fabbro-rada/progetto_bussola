import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useFetchOnMount } from '../../hooks/useFetchOnMount'

export function MetricsPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const fetchMetrics = useCallback(() => client.getMetrics(), [client])
  const { data: metrics, error } = useFetchOnMount(fetchMetrics, (r) => r.metrics)

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
