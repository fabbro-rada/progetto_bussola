import { useTranslation } from 'react-i18next'
import { Notice } from '../components/Notice'

export function Unauthorized() {
  const { t } = useTranslation()
  return <Notice tone="error" text={t('unauthorized.text')} />
}
