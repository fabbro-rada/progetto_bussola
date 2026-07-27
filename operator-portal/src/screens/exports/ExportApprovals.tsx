import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { ExportRequest } from '../../types'
import { ConfirmDialog } from '../operators/ConfirmDialog'
import { DenyDialog } from './DenyDialog'
import { filterSummary } from './filterSummary'

export function ExportApprovals() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [pending, setPending] = useState<ExportRequest[] | null>(null)
  const [error, setError] = useState('')
  const [approving, setApproving] = useState<ExportRequest | null>(null)
  const [denying, setDenying] = useState<ExportRequest | null>(null)

  const onErr = useCallback(
    (status: 'unauthorized' | 'forbidden' | 'error') => {
      const outcome = handleError(status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    },
    [handleError, t],
  )

  const load = useCallback(async () => {
    setError('')
    const r = await client.listPendingExports()
    if (r.status === 'ok') setPending(r.requests)
    else onErr(r.status)
  }, [client, onErr])

  useEffect(() => {
    void load()
  }, [load])

  async function confirmApprove() {
    if (!approving) return
    const req = approving
    setApproving(null)
    const r = await client.approveExport(req.id)
    if (r.status === 'ok' || r.status === 'conflict' || r.status === 'not-found') void load()
    else onErr(r.status)
  }

  async function confirmDeny(reason: string) {
    if (!denying) return
    const req = denying
    setDenying(null)
    const r = await client.denyExport(req.id, reason)
    if (r.status === 'ok' || r.status === 'conflict' || r.status === 'not-found') void load()
    else onErr(r.status)
  }

  return (
    <div className="op-admin">
      <h1>{t('exports.approvalsTitle')}</h1>

      {error && <p className="error" role="alert">{error}</p>}
      {pending === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        pending &&
        (pending.length === 0 ? (
          <p>{t('exports.emptyPending')}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t('exports.colRequester')}</th>
                <th>{t('exports.colFilters')}</th>
                <th>{t('exports.colReason')}</th>
                <th>{t('exports.colDate')}</th>
                <th>{t('exports.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {pending.map((req) => (
                <tr key={req.id}>
                  <td>{req.requested_by}</td>
                  <td>{filterSummary(req.filters, t)}</td>
                  <td>{req.reason}</td>
                  <td>{req.created_at.slice(0, 10)}</td>
                  <td className="op-actions">
                    <button type="button" onClick={() => setApproving(req)}>{t('exports.approve')}</button>
                    <button type="button" onClick={() => setDenying(req)}>{t('exports.deny')}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))
      )}

      {approving && (
        <ConfirmDialog
          message={t('exports.confirmApprove', {
            who: approving.requested_by,
            scope: filterSummary(approving.filters, t),
            reason: approving.reason,
          })}
          confirmLabel={t('exports.confirm')}
          onConfirm={confirmApprove}
          onCancel={() => setApproving(null)}
        />
      )}
      {denying && (
        <DenyDialog
          title={t('exports.denyTitle', { who: denying.requested_by })}
          onConfirm={confirmDeny}
          onCancel={() => setDenying(null)}
        />
      )}
    </div>
  )
}
