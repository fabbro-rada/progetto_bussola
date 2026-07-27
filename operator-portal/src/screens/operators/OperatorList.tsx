import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { CreateOperatorRequest, Operator } from '../../types'
import { CreateOperatorForm } from './CreateOperatorForm'
import { ConfirmDialog } from './ConfirmDialog'
import { TempPasswordModal } from './TempPasswordModal'

type Pending = { kind: 'disable' | 'enable' | 'reset'; op: Operator } | null
type TempPw = { password: string; subtitle: string } | null

export function OperatorList() {
  const { t } = useTranslation()
  const { client, operator: me } = useAuth()
  const handleError = useApiError()
  const [operators, setOperators] = useState<Operator[] | null>(null)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [createError, setCreateError] = useState('')
  const [pending, setPending] = useState<Pending>(null)
  const [tempPw, setTempPw] = useState<TempPw>(null)

  const onErr = useCallback(
    (status: 'unauthorized' | 'forbidden' | 'error', set: (m: string) => void) => {
      const outcome = handleError(status)
      if (outcome !== 'handled') set(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    },
    [handleError, t],
  )

  const load = useCallback(async () => {
    setError('')
    const r = await client.listOperators()
    if (r.status === 'ok') setOperators(r.operators)
    else onErr(r.status, setError)
  }, [client, onErr])

  useEffect(() => {
    void load()
  }, [load])

  async function create(body: CreateOperatorRequest) {
    setCreateError('')
    setCreateBusy(true)
    const r = await client.createOperator(body)
    setCreateBusy(false)
    if (r.status === 'ok') {
      setShowCreate(false)
      setTempPw({ password: r.created.temp_password, subtitle: t('operators.createdSubtitle', { name: r.created.operator.username }) })
      void load()
    } else onErr(r.status, setCreateError)
  }

  async function runPending() {
    if (!pending) return
    const { kind, op } = pending
    setPending(null)
    if (kind === 'reset') {
      const r = await client.resetPassword(op.id)
      if (r.status === 'ok') {
        setTempPw({ password: r.temp_password, subtitle: t('operators.resetSubtitle', { name: op.username }) })
        void load()
      } else onErr(r.status, setError)
      return
    }
    const r = kind === 'disable' ? await client.disableOperator(op.id) : await client.enableOperator(op.id)
    if (r.status === 'ok') void load()
    else onErr(r.status, setError)
  }

  const confirmMessage = pending
    ? t(
        pending.kind === 'disable'
          ? 'operators.confirmDisable'
          : pending.kind === 'enable'
            ? 'operators.confirmEnable'
            : 'operators.confirmReset',
        { name: pending.op.username },
      )
    : ''

  return (
    <div className="op-admin">
      <div className="op-head">
        <h1>{t('operators.title')}</h1>
        <button
          type="button"
          onClick={() => {
            setShowCreate((s) => !s)
            setCreateError('')
          }}
        >
          + {t('operators.new')}
        </button>
      </div>

      {showCreate && (
        <CreateOperatorForm
          onSubmit={create}
          onCancel={() => {
            setShowCreate(false)
            setCreateError('')
          }}
          busy={createBusy}
          error={createError}
        />
      )}

      {error && <p className="error" role="alert">{error}</p>}
      {operators === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        operators &&
        (operators.length === 0 ? (
          <p>{t('operators.empty')}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t('operators.colUsername')}</th>
                <th>{t('operators.colName')}</th>
                <th>{t('operators.colRole')}</th>
                <th>{t('operators.colStatus')}</th>
                <th>{t('operators.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {operators.map((op) => {
                const isSelf = me?.id === op.id
                const selfTitle = isSelf ? t('operators.selfActionBlocked') : undefined
                return (
                  <tr key={op.id}>
                    <td>{op.username}</td>
                    <td>{op.display_name}</td>
                    <td>{t(`shell.role.${op.role}`)}</td>
                    <td>
                      {op.is_active ? (
                        <span className="st-active">● {t('operators.active')}</span>
                      ) : (
                        <span className="st-disabled">○ {t('operators.disabled')}</span>
                      )}
                      {op.must_change_password && <span className="badge-mc">{t('operators.mustChange')}</span>}
                    </td>
                    <td className="op-actions">
                      {op.is_active ? (
                        <button type="button" disabled={isSelf} title={selfTitle} onClick={() => setPending({ kind: 'disable', op })}>
                          {t('operators.disable')}
                        </button>
                      ) : (
                        <button type="button" onClick={() => setPending({ kind: 'enable', op })}>{t('operators.enable')}</button>
                      )}
                      <button type="button" disabled={isSelf} title={selfTitle} onClick={() => setPending({ kind: 'reset', op })}>
                        {t('operators.resetPassword')}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ))
      )}

      {pending && (
        <ConfirmDialog message={confirmMessage} confirmLabel={t('operators.confirm')} onConfirm={runPending} onCancel={() => setPending(null)} />
      )}
      {tempPw && <TempPasswordModal password={tempPw.password} subtitle={tempPw.subtitle} onClose={() => setTempPw(null)} />}
    </div>
  )
}
