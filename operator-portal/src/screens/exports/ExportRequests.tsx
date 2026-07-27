import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { ExportRequest, ProfileFilters } from '../../types'
import { NewExportForm } from './NewExportForm'
import { filterSummary } from './filterSummary'
import { saveBlob as defaultSaveBlob } from './download'

export function ExportRequests({ saveBlob = defaultSaveBlob }: { saveBlob?: (blob: Blob, filename: string) => void }) {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [requests, setRequests] = useState<ExportRequest[] | null>(null)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [createError, setCreateError] = useState('')

  const onErr = useCallback(
    (status: 'unauthorized' | 'forbidden' | 'error', set: (m: string) => void) => {
      const outcome = handleError(status)
      if (outcome !== 'handled') set(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    },
    [handleError, t],
  )

  const load = useCallback(async () => {
    setError('')
    const r = await client.listExports()
    if (r.status === 'ok') setRequests(r.requests)
    else onErr(r.status, setError)
  }, [client, onErr])

  useEffect(() => {
    void load()
  }, [load])

  async function create(filters: ProfileFilters, reason: string) {
    setCreateError('')
    setCreateBusy(true)
    const r = await client.createExport(filters, reason)
    setCreateBusy(false)
    if (r.status === 'ok') {
      setShowCreate(false)
      void load()
    } else onErr(r.status, setCreateError)
  }

  async function download(req: ExportRequest) {
    setError('')
    const r = await client.downloadExport(req.id)
    if (r.status === 'ok') saveBlob(r.blob, `export-${req.id}.json`)
    else if (r.status === 'unauthorized') handleError(r.status)
    else setError(t(r.status === 'forbidden' ? 'errors.forbidden' : 'exports.downloadError'))
  }

  return (
    <div className="op-admin">
      <div className="op-head">
        <h1>{t('exports.title')}</h1>
        <button type="button" onClick={() => { setShowCreate((s) => !s); setCreateError('') }}>+ {t('exports.new')}</button>
      </div>

      {showCreate && <NewExportForm onSubmit={create} onCancel={() => { setShowCreate(false); setCreateError('') }} busy={createBusy} error={createError} />}

      {error && <p className="error" role="alert">{error}</p>}
      {requests === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        requests &&
        (requests.length === 0 ? (
          <p>{t('exports.empty')}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t('exports.colDate')}</th>
                <th>{t('exports.colFilters')}</th>
                <th>{t('exports.colStatus')}</th>
                <th>{t('exports.colOutcome')}</th>
                <th>{t('exports.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => (
                <tr key={req.id}>
                  <td>{req.created_at.slice(0, 10)}</td>
                  <td>{filterSummary(req.filters, t)}</td>
                  <td><span className={`badge-status st-${req.status}`}>{t(`exports.status_${req.status}`)}</span></td>
                  <td>{req.decision_reason ?? '—'}</td>
                  <td>{req.status === 'approved' && <button type="button" onClick={() => download(req)}>{t('exports.download')}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))
      )}
    </div>
  )
}
