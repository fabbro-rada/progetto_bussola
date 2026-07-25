import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function Login() {
  const { t } = useTranslation()
  const { operator, mustChangePassword, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (operator) return <Navigate to={mustChangePassword ? '/change-password' : '/'} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    const r = await login(username, password)
    setBusy(false)
    if (r.status === 'ok') navigate(r.mustChangePassword ? '/change-password' : '/', { replace: true })
    else if (r.status === 'invalid') setError(t('errors.invalidCredentials'))
    else setError(t('errors.generic'))
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <h1>{t('login.title')}</h1>
      <label>
        {t('login.username')}
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
      </label>
      <label>
        {t('login.password')}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || !username || !password}>
        {t('login.submit')}
      </button>
    </form>
  )
}
