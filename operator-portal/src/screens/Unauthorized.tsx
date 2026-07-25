import { useTranslation } from 'react-i18next'

export function Unauthorized() {
  const { t } = useTranslation()
  return <p role="alert">{t('unauthorized.text')}</p>
}
