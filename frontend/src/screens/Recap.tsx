import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { VoiceBar } from '../components/VoiceBar'
import type { WorkProfileView } from '../types'

export function Recap({ profile, onSubmit, busy }: { profile: WorkProfileView; onSubmit: (a: string) => void; busy?: boolean }) {
  const { t } = useTranslation()
  const [correcting, setCorrecting] = useState(false)
  const [value, setValue] = useState('')
  const [voiceBusy, setVoiceBusy] = useState(false)
  const trimmed = value.trim()

  const lines: string[] = []
  const push = (label: string, val: string) => { if (val) lines.push(`${label}: ${val}`) }
  push(t('recap.skills'), profile.skills.map((s) => s.name).join(', '))
  push(t('recap.languages'), profile.languages.map((l) => `${l.language} (${t('recap.level_' + l.level)})`).join(', '))
  if (profile.digital_literacy) push(t('recap.digitalLiteracy'), t('recap.digital_' + profile.digital_literacy))
  push(t('recap.experiences'), profile.experiences.map((e) => `${e.role} — ${e.sector} — ${t('recap.months', { n: e.duration_months })}`).join('; '))
  if (profile.aspiration) {
    push(t('recap.aspiration'), profile.aspiration.fields_of_interest.join(', '))
    if (profile.aspiration.availability) push(t('recap.availability'), t('recap.availability_' + profile.aspiration.availability))
    push(t('recap.constraints'), profile.aspiration.constraints.map((c) => t('recap.constraint_' + c)).join(', '))
  }
  push(t('recap.training'), profile.desired_training.map((d) => d.topic).join(', '))
  push(t('recap.notes'), profile.operational_notes.map((n) => t('recap.note_' + n)).join(', '))
  const spoken = [t('recap.title'), ...lines].join('. ')

  return (
    <div className="recap">
      <h1>{t('recap.title')}</h1>
      {!correcting ? (
        <>
          <VoiceBar text={spoken} disabled={busy} />
          <ul className="recap-list">
            {lines.map((line) => <li key={line}>{line}</li>)}
          </ul>
          <BigButton variant="confirm" disabled={busy} onClick={() => onSubmit(t('recap.confirm'))}>{t('recap.confirm')}</BigButton>
          <BigButton variant="secondary" disabled={busy} onClick={() => setCorrecting(true)}>{t('recap.correct')}</BigButton>
        </>
      ) : (
        <>
          <VoiceBar text={spoken} canDictate onDictated={setValue} onBusyChange={setVoiceBusy} disabled={busy} />
          <textarea aria-label={t('recap.correctPlaceholder')} placeholder={t('recap.correctPlaceholder')}
            value={value} disabled={voiceBusy || busy} onChange={(e) => setValue(e.target.value)} />
          <BigButton variant="confirm" disabled={!trimmed || busy || voiceBusy} onClick={() => onSubmit(trimmed)}>{t('recap.send')}</BigButton>
        </>
      )}
    </div>
  )
}
