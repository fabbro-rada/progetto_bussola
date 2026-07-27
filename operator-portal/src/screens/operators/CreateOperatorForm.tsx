import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { CreateOperatorRequest, Role } from '../../types'

const ROLES: Role[] = ['operator', 'supervisor', 'admin', 'auditor']

export function CreateOperatorForm({
  onSubmit,
  onCancel,
  busy,
  error,
}: {
  onSubmit: (body: CreateOperatorRequest) => void
  onCancel: () => void
  busy: boolean
  error: string
}) {
  const { t } = useTranslation()
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<Role | ''>('')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !displayName.trim() || !role) return
    onSubmit({ username: username.trim(), display_name: displayName.trim(), role })
  }

  return (
    <form className="op-create" onSubmit={submit}>
      <h2>{t('operators.createTitle')}</h2>
      <label>{t('operators.username')}<input value={username} onChange={(e) => setUsername(e.target.value)} /></label>
      <label>{t('operators.displayName')}<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></label>
      <label>{t('operators.role')}
        <select value={role} onChange={(e) => setRole(e.target.value as Role | '')}>
          <option value="">{t('operators.rolePlaceholder')}</option>
          {ROLES.map((r) => <option key={r} value={r}>{t(`shell.role.${r}`)}</option>)}
        </select>
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="op-create-actions">
        <button type="button" onClick={onCancel}>{t('operators.cancel')}</button>
        <button type="submit" disabled={busy || !username.trim() || !displayName.trim() || !role}>{t('operators.create')}</button>
      </div>
    </form>
  )
}
