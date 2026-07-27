import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { AuditEntry, AuditFilters, AuditVerification } from '../../types'
import { detailsSummary } from './detailsSummary'

export const LIMIT = 50

export function AuditLog() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const [actor, setActor] = useState('')
  const [action, setAction] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [verification, setVerification] = useState<AuditVerification | null>(null)
  const [applied, setApplied] = useState<AuditFilters>({ limit: LIMIT })

  const onErr = useCallback(
    (status: 'unauthorized' | 'forbidden' | 'error') => {
      const outcome = handleError(status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    },
    [handleError, t],
  )

  const currentFilters = useCallback((): AuditFilters => {
    const f: AuditFilters = { limit: LIMIT }
    if (actor.trim()) f.actor = actor.trim()
    if (action.trim()) f.action = action.trim()
    if (from) f.from = from
    if (to) f.to = to
    return f
  }, [actor, action, from, to])

  const runSearch = useCallback(
    async (filters: AuditFilters) => {
      setError('')
      setApplied(filters)
      const r = await client.listAudit(filters)
      if (r.status === 'ok') {
        setEntries(r.entries)
        setHasMore(r.entries.length === LIMIT)
      } else onErr(r.status)
    },
    [client, onErr],
  )

  useEffect(() => {
    void runSearch({ limit: LIMIT })
  }, [runSearch])

  function submit(e: FormEvent) {
    e.preventDefault()
    void runSearch(currentFilters())
  }

  async function loadMore() {
    if (!entries || entries.length === 0) return
    const before = entries[entries.length - 1].id
    const r = await client.listAudit({ ...applied, before })
    if (r.status === 'ok') {
      const page = r.entries
      setEntries((prev) => [...(prev ?? []), ...page])
      setHasMore(page.length === LIMIT)
    } else onErr(r.status)
  }

  async function verify() {
    setError('')
    const r = await client.verifyAudit()
    if (r.status === 'ok') setVerification(r.verification)
    else onErr(r.status)
  }

  return (
    <div className="audit-log">
      <h1>{t('audit.title')}</h1>
      <div className="audit-toolbar">
        <form className="filters" onSubmit={submit}>
          <label>{t('audit.filterActor')}<input value={actor} onChange={(e) => setActor(e.target.value)} /></label>
          <label>{t('audit.filterAction')}<input value={action} onChange={(e) => setAction(e.target.value)} /></label>
          <label>{t('audit.filterFrom')}<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label>{t('audit.filterTo')}<input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
          <button type="submit">{t('audit.search')}</button>
        </form>
        <div className="audit-verify">
          <button type="button" onClick={verify}>{t('audit.verify')}</button>
          {verification &&
            (verification.ok ? (
              <span className="badge-status st-approved">{t('audit.verifyOk')}</span>
            ) : (
              <span className="badge-danger" role="alert">{t('audit.verifyBroken', { id: verification.broken_at })}</span>
            ))}
        </div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {entries === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        entries &&
        (entries.length === 0 ? (
          <p>{t('audit.empty')}</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>{t('audit.colWhen')}</th>
                  <th>{t('audit.colActor')}</th>
                  <th>{t('audit.colAction')}</th>
                  <th>{t('audit.colTarget')}</th>
                  <th>{t('audit.colDetails')}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id}>
                    <td>{e.occurred_at.replace('T', ' ').slice(0, 16)}</td>
                    <td>{e.actor ?? t('audit.none')}</td>
                    <td>{e.action}</td>
                    <td>{e.target_pseudonym ?? t('audit.none')}</td>
                    <td>{detailsSummary(e.details)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {hasMore && (
              <button type="button" className="audit-more" onClick={loadMore}>{t('audit.loadMore')}</button>
            )}
          </>
        ))
      )}
    </div>
  )
}
