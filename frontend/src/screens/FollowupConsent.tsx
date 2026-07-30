import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { VoiceBar } from '../components/VoiceBar'

const POINTS = ['recent', 'onlyWork', 'voluntary', 'local'] as const

// Follow-up consent/recap (§4 voluntariness): shown after the person has
// entered a valid-looking code+language but BEFORE any request reaches the
// backend. Declining is a first-class, consequence-free path — the wiring in
// App.tsx routes it to the same reset `declineConsent` uses, so no
// start-followup call is ever made and nothing about the person is touched.
export function FollowupConsent({
  onAccept,
  onDecline,
  busy,
}: {
  onAccept: () => void
  onDecline: () => void
  busy?: boolean
}) {
  const { t } = useTranslation()
  const spoken = [t('followupConsent.title'), ...POINTS.map((p) => t(`followupConsent.point.${p}`))].join('. ')
  return (
    <div className="consent followup-consent">
      <h1>{t('followupConsent.title')}</h1>
      <ul>
        {POINTS.map((p) => (
          <li key={p}>{t(`followupConsent.point.${p}`)}</li>
        ))}
      </ul>
      <VoiceBar text={spoken} />
      <BigButton variant="confirm" disabled={busy} onClick={onAccept}>
        {t('followupConsent.accept')}
      </BigButton>
      <BigButton variant="secondary" onClick={onDecline}>
        {t('followupConsent.decline')}
      </BigButton>
    </div>
  )
}
