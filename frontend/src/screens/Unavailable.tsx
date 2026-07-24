import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { Notice } from '../components/Notice'

export function Unavailable({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <Notice tone="info" text={t('unavailable.text')}>
      <BigButton variant="confirm" onClick={onRetry}>
        {t('unavailable.retry')}
      </BigButton>
    </Notice>
  )
}
