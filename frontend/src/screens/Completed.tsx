import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { Notice } from '../components/Notice'
import { VoiceBar } from '../components/VoiceBar'

export function Completed({ onFinish }: { onFinish: () => void }) {
  const { t } = useTranslation()
  return (
    <Notice tone="success" text={t('completed.text')}>
      <VoiceBar text={t('completed.text')} />
      <BigButton variant="confirm" onClick={onFinish}>
        {t('completed.finish')}
      </BigButton>
    </Notice>
  )
}
