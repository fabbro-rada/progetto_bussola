import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { WorkProfile } from '../../types'
import { SkillBadge } from './SkillBadge'

export function ProfileDetail() {
  const { t } = useTranslation()
  const { pseudonym } = useParams()
  const { client } = useAuth()
  const handleError = useApiError()
  const [profile, setProfile] = useState<WorkProfile | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void client.getProfile(pseudonym ?? '').then((r) => {
      if (!active) return
      if (r.status === 'ok') setProfile(r.profile)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled')
          setError(t(outcome === 'not-found' ? 'profiles.notFound' : outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    })
    return () => { active = false }
  }, [client, handleError, pseudonym, t])

  if (error) return <p className="error" role="alert">{error}</p>
  if (profile === null) return <p>{t('common.loading')}</p>

  return (
    <div className="profile-detail">
      <p><Link to="/profiles">← {t('profiles.title')}</Link></p>
      <div className="pd-head">
        <h1>{profile.pseudonym_id}</h1>
        <span>{t('profiles.digitalLiteracy')}: {profile.digital_literacy ? t(`pl.digital_${profile.digital_literacy}`) : t('profiles.none')}</span>
      </div>

      <h2>{t('profiles.skills')}</h2>
      <ul className="skills">
        {profile.skills.map((s, i) => (
          <li key={i}>
            <span className="skill-name">{s.name}</span> <span className="muted">· {t(`pl.kind_${s.kind}`)}</span> <SkillBadge grade={s.evidence} />
          </li>
        ))}
      </ul>

      <h2>{t('profiles.languages')}</h2>
      <ul>{profile.languages.map((l, i) => <li key={i}>{l.language} — {t(`pl.level_${l.level}`)}</li>)}</ul>

      <h2>{t('profiles.experiences')}</h2>
      <ul>{profile.experiences.map((e, i) => <li key={i}><span className="exp-role">{e.role}</span> — {e.sector} — {t('profiles.months', { n: e.duration_months })}</li>)}</ul>

      {profile.aspiration && (
        <>
          <h2>{t('profiles.aspiration')}</h2>
          <p>{t('profiles.interests')}: {profile.aspiration.fields_of_interest.join(', ') || t('profiles.none')}</p>
          <p>{t('profiles.colAvailability')}: {profile.aspiration.availability ? t(`pl.availability_${profile.aspiration.availability}`) : t('profiles.none')}</p>
          <p>{t('profiles.constraints')}: {profile.aspiration.constraints.map((c) => t(`pl.constraint_${c}`)).join(', ') || t('profiles.none')}</p>
        </>
      )}

      {profile.desired_training.length > 0 && (
        <>
          <h2>{t('profiles.training')}</h2>
          <ul>{profile.desired_training.map((d, i) => <li key={i}>{d.topic}</li>)}</ul>
        </>
      )}

      {profile.operational_notes.length > 0 && (
        <>
          <h2>{t('profiles.notes')}</h2>
          <ul>{profile.operational_notes.map((n, i) => <li key={i}>{t(`pl.note_${n}`)}</li>)}</ul>
        </>
      )}
    </div>
  )
}
