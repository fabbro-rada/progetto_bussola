import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'

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
  return (
    <div className="consent">
      <h1>{t('consent.title')}</h1>
      <ul>
        {POINTS.map((p) => (
          <li key={p}>{t(`consent.point.${p}`)}</li>
        ))}
      </ul>
      <BigButton variant="confirm" disabled={busy} onClick={onAccept}>
        {t('consent.accept')}
      </BigButton>
      <BigButton variant="secondary" onClick={onDecline}>
        {t('consent.decline')}
      </BigButton>
    </div>
  )
}
