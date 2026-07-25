import { useTranslation } from 'react-i18next'
import { Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Nav } from './Nav'

export function AppShell() {
  const { t } = useTranslation()
  const { operator, logout } = useAuth()
  return (
    <div className="shell">
      <header className="shell-header">
        <span className="brand">Bussola</span>
        {operator && (
          <span className="who">
            {operator.display_name} · {t(`shell.role.${operator.role}`)}
          </span>
        )}
        <button className="logout" onClick={() => void logout()}>
          {t('shell.logout')}
        </button>
      </header>
      <div className="shell-body">
        <Nav />
        <main className="shell-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
