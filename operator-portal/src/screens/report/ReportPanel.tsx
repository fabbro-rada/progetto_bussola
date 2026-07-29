import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import { useFetchOnMount } from '../../hooks/useFetchOnMount'
import type { Count } from '../../types'

// A suppressed small cell is the STRING "<5" (anonymity, k=5 small-cell
// suppression, enforced server-side in bussola.report.service.suppress).
// Render it verbatim — never compute or expand it here (§ global constraint).
function renderCount(value: Count): string {
  return typeof value === 'number' ? String(value) : value
}

function DistributionTable({ title, data }: { title: string; data: Record<string, Count> }) {
  const entries = Object.entries(data)
  return (
    <section className="report-section">
      <h2>{title}</h2>
      {entries.length === 0 ? (
        <p>—</p>
      ) : (
        <table>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td>{key}</td>
                <td>{renderCount(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

export function ReportPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const fetchReport = useCallback(() => client.getReport(), [client])
  const { data: report, error } = useFetchOnMount(fetchReport, (r) => r.report)

  const [exportBusy, setExportBusy] = useState(false)
  const [exportError, setExportError] = useState('')
  const [exportPending, setExportPending] = useState(false)

  async function onExport() {
    setExportError('')
    setExportBusy(true)
    const r = await client.createReportExport()
    setExportBusy(false)
    if (r.status === 'ok') {
      setExportPending(true)
    } else {
      const outcome = handleError(r.status)
      if (outcome !== 'handled') setExportError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    }
  }

  return (
    <div className="report">
      <h1>{t('report.title')}</h1>
      {error && <p className="error" role="alert">{error}</p>}
      {report === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        report && (
          <>
            <section className="report-section">
              <h2>{t('report.coverage')}</h2>
              <div className="metric-cards">
                <div className="metric-card">
                  <span className="metric-value">{report.coverage.total_profiles}</span>
                  <span className="metric-label">{t('report.totalProfiles')}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-value">{report.coverage.completed_profiles}</span>
                  <span className="metric-label">{t('report.completedProfiles')}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-value">{Math.round(report.coverage.average_completeness * 100)}%</span>
                  <span className="metric-label">{t('report.averageCompleteness')}</span>
                </div>
              </div>
            </section>

            <DistributionTable title={t('report.completenessHistogram')} data={report.coverage.completeness_histogram} />
            <DistributionTable title={t('report.languages')} data={report.languages} />
            <DistributionTable title={t('report.skillKinds')} data={report.skill_kinds} />
            <DistributionTable title={t('report.skillEvidence')} data={report.skill_evidence} />
            <DistributionTable title={t('report.availability')} data={report.availability} />
            <DistributionTable title={t('report.constraints')} data={report.constraints} />

            <section className="report-section">
              <h2>{t('report.matching')}</h2>
              <div className="metric-cards">
                <div className="metric-card">
                  <span className="metric-value">{report.total_job_requests}</span>
                  <span className="metric-label">{t('report.totalJobRequests')}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-value">{report.matching.runs}</span>
                  <span className="metric-label">{t('report.matchingRuns')}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-value">{report.matching.evaluated}</span>
                  <span className="metric-label">{t('report.matchingEvaluated')}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-value">{report.matching.compatible}</span>
                  <span className="metric-label">{t('report.matchingCompatible')}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-value">{Math.round(report.matching.compatible_rate * 100)}%</span>
                  <span className="metric-label">{t('report.matchingCompatibleRate')}</span>
                </div>
              </div>
            </section>
            <DistributionTable title={t('report.topGaps')} data={report.matching.top_gaps} />

            <section className="report-section">
              <h2>{t('report.trends')}</h2>
            </section>
            <DistributionTable title={t('report.profilesByWeek')} data={report.trends.profiles_by_week} />
            <DistributionTable title={t('report.jobRequestsByWeek')} data={report.trends.job_requests_by_week} />

            <section className="report-section">
              <button type="button" onClick={() => void onExport()} disabled={exportBusy}>
                {t('report.export')}
              </button>
              {exportError && <p className="error" role="alert">{exportError}</p>}
              {exportPending && <p>{t('report.exportPending')}</p>}
            </section>
          </>
        )
      )}
    </div>
  )
}
