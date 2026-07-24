import { useTranslation } from 'react-i18next'
import { Notice } from '../components/Notice'
import { VoiceBar } from '../components/VoiceBar'

export function Unauthorized() {
  const { t } = useTranslation()
  return (
    <Notice tone="error" text={t('unauthorized.text')}>
      <VoiceBar text={t('unauthorized.text')} />
    </Notice>
  )
}
