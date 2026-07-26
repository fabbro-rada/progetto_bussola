import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { Availability, OperationalNoteCategory, ProfileFilters, WorkProfile } from '../../types'

const AVAILABILITIES: Availability[] = ['full_time', 'part_time', 'flexible']
const NOTES: OperationalNoteCategory[] = [
  'needs_language_support', 'needs_literacy_support', 'limited_availability', 'prefers_team_work', 'prefers_solo_work',
]

export function ProfileSearch() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [availability, setAvailability] = useState<Availability | ''>('')
  const [language, setLanguage] = useState('')
  const [note, setNote] = useState<OperationalNoteCategory | ''>('')
  const [skillQuery, setSkillQuery] = useState('')
  const [profiles, setProfiles] = useState<WorkProfile[] | null>(null)
  const [error, setError] = useState('')

  const runSearch = useCallback(
    async (filters: ProfileFilters) => {
      setError('')
      const r = await client.searchProfiles(filters)
      if (r.status === 'ok') setProfiles(r.profiles)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    },
    [client, handleError, t],
  )

  useEffect(() => {
    void runSearch({}) // full list on mount (allowed + audited, §7.3)
  }, [runSearch])

  function submit(e: FormEvent) {
    e.preventDefault()
    const filters: ProfileFilters = {}
    if (availability) filters.availability = availability
    if (language.trim()) filters.language = language.trim()
    if (note) filters.note = note
    if (skillQuery.trim()) filters.skill_query = skillQuery.trim()
    void runSearch(filters)
  }

  return (
    <div className="profile-search">
      <h1>{t('profiles.title')}</h1>
      <form className="filters" onSubmit={submit}>
        <label>{t('profiles.filterAvailability')}
          <select value={availability} onChange={(e) => setAvailability(e.target.value as Availability | '')}>
            <option value="">{t('profiles.any')}</option>
            {AVAILABILITIES.map((a) => <option key={a} value={a}>{t(`pl.availability_${a}`)}</option>)}
          </select>
        </label>
        <label>{t('profiles.filterLanguage')}<input value={language} onChange={(e) => setLanguage(e.target.value)} /></label>
        <label>{t('profiles.filterNote')}
          <select value={note} onChange={(e) => setNote(e.target.value as OperationalNoteCategory | '')}>
            <option value="">{t('profiles.any')}</option>
            {NOTES.map((n) => <option key={n} value={n}>{t(`pl.note_${n}`)}</option>)}
          </select>
        </label>
        <label>{t('profiles.filterSkill')}<input value={skillQuery} onChange={(e) => setSkillQuery(e.target.value)} /></label>
        <button type="submit">{t('profiles.search')}</button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      {profiles === null ? (
        <p>{t('common.loading')}</p>
      ) : profiles.length === 0 ? (
        <p>{t('profiles.empty')}</p>
      ) : (
        <table>
          <thead>
            <tr><th>{t('profiles.colPseudonym')}</th><th>{t('profiles.colLanguages')}</th><th>{t('profiles.colAvailability')}</th><th>{t('profiles.colSkills')}</th></tr>
          </thead>
          <tbody>
            {profiles.map((p) => (
              <tr key={p.pseudonym_id}>
                <td><Link to={`/profiles/${p.pseudonym_id}`}>{p.pseudonym_id}</Link></td>
                <td>{p.languages.map((l) => l.language).join(', ') || t('profiles.none')}</td>
                <td>{p.aspiration?.availability ? t(`pl.availability_${p.aspiration.availability}`) : t('profiles.none')}</td>
                <td>{t('profiles.skillsCount', { n: p.skills.length })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
