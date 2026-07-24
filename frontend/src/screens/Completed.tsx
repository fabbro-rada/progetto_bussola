import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { Notice } from '../components/Notice'

export function Completed({ onFinish }: { onFinish: () => void }) {
  const { t } = useTranslation()
  return (
    <Notice tone="success" text={t('completed.text')}>
      <BigButton variant="confirm" onClick={onFinish}>
        {t('completed.finish')}
      </BigButton>
    </Notice>
  )
}
