import { type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function ProtectedRoute({ children, allowMustChange = false }: { children: ReactNode; allowMustChange?: boolean }) {
  const { t } = useTranslation()
  const { operator, loading, mustChangePassword } = useAuth()
  if (loading) return <p>{t('common.loading')}</p>
  if (!operator) return <Navigate to="/login" replace />
  if (mustChangePassword && !allowMustChange) return <Navigate to="/change-password" replace />
  return <>{children}</>
}
