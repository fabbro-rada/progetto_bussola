import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function ChangePassword() {
  const { t } = useTranslation()
  const { changePassword, clearMustChangePassword, onUnauthorized } = useAuth()
  const navigate = useNavigate()
  const [oldPassword, setOld] = useState('')
  const [newPassword, setNew] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const MIN_LENGTH = 8

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (newPassword.length < MIN_LENGTH) {
      // Mirror the backend rule (ChangePasswordRequest new_password min_length=8)
      // with a clear message, instead of the generic error the 422 would map to.
      setError(t('changePassword.tooShort', { min: MIN_LENGTH }))
      return
    }
    setBusy(true)
    const r = await changePassword(oldPassword, newPassword)
    setBusy(false)
    if (r.status === 'ok') {
      clearMustChangePassword()
      navigate('/', { replace: true })
    } else if (r.status === 'unauthorized') {
      onUnauthorized()
      navigate('/login', { replace: true })
    } else {
      setError(t('errors.generic'))
    }
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <h1>{t('changePassword.title')}</h1>
      <p>{t('changePassword.intro')}</p>
      <label>
        {t('changePassword.old')}
        <input type="password" value={oldPassword} onChange={(e) => setOld(e.target.value)} autoComplete="current-password" />
      </label>
      <label>
        {t('changePassword.new')}
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNew(e.target.value)}
          autoComplete="new-password"
          minLength={8}
        />
      </label>
      <small className="hint">{t('changePassword.hint', { min: 8 })}</small>
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || !oldPassword || !newPassword}>
        {t('changePassword.submit')}
      </button>
    </form>
  )
}
