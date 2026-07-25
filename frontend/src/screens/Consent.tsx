import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { VoiceBar } from '../components/VoiceBar'

const POINTS = ['work', 'purpose', 'onlyWork', 'voluntary', 'local'] as const

export function Consent({
  onAccept,
  onDecline,
  busy,
}: {
  onAccept: () => void
  onDecline: () => void
  busy?: boolean
}) {
  const { t } = useTranslation()
  const spoken = [t('consent.title'), ...POINTS.map((p) => t(`consent.point.${p}`))].join('. ')
  return (
    <div className="consent">
      <h1>{t('consent.title')}</h1>
      <ul>
        {POINTS.map((p) => (
          <li key={p}>{t(`consent.point.${p}`)}</li>
        ))}
      </ul>
      <VoiceBar text={spoken} />
      <BigButton variant="confirm" disabled={busy} onClick={onAccept}>
        {t('consent.accept')}
      </BigButton>
      <BigButton variant="secondary" onClick={onDecline}>
        {t('consent.decline')}
      </BigButton>
    </div>
  )
}
