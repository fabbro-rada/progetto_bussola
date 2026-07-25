import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'

export function Home() {
  const { t } = useTranslation()
  const { operator } = useAuth()
  return <h1>{t('home.welcome', { name: operator?.display_name ?? '' })}</h1>
}
