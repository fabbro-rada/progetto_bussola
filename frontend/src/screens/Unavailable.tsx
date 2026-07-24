import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { Notice } from '../components/Notice'
import { VoiceBar } from '../components/VoiceBar'

export function Unavailable({ onRetry, busy }: { onRetry: () => void; busy?: boolean }) {
  const { t } = useTranslation()
  return (
    <Notice tone="info" text={t('unavailable.text')}>
      <VoiceBar text={t('unavailable.text')} />
      <BigButton variant="confirm" disabled={busy} onClick={onRetry}>
        {t('unavailable.retry')}
      </BigButton>
    </Notice>
  )
}
