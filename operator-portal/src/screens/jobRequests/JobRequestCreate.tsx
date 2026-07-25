import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { Availability, LanguageLevel, RequiredLanguage } from '../../types'

const LEVELS: LanguageLevel[] = ['basic', 'intermediate', 'fluent', 'native']
const AVAILABILITIES: Availability[] = ['full_time', 'part_time', 'flexible']

function splitCsv(s: string): string[] {
  return s.split(',').map((x) => x.trim()).filter(Boolean)
}

export function JobRequestCreate() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [sector, setSector] = useState('')
  const [description, setDescription] = useState('')
  const [skills, setSkills] = useState('')
  const [prerequisites, setPrerequisites] = useState('')
  const [languages, setLanguages] = useState<RequiredLanguage[]>([])
  const [availability, setAvailability] = useState<Availability | ''>('')
  const [nightShifts, setNightShifts] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function addLanguage() {
    setLanguages((ls) => [...ls, { language: '', min_level: 'basic' }])
  }
  function updateLanguage(i: number, patch: Partial<RequiredLanguage>) {
    setLanguages((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }
  function removeLanguage(i: number) {
    setLanguages((ls) => ls.filter((_, idx) => idx !== i))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    const body = {
      title,
      sector,
      description,
      required_skills: splitCsv(skills),
      required_languages: languages.filter((l) => l.language.trim() !== ''),
      required_availability: availability === '' ? null : availability,
      involves_night_shifts: nightShifts,
      training_prerequisites: splitCsv(prerequisites),
    }
    const r = await client.createJobRequest(body)
    setBusy(false)
    if (r.status === 'ok') navigate(`/job-requests/${r.job.id}`, { replace: true })
    else {
      const outcome = handleError(r.status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    }
  }

  return (
    <form className="job-form" onSubmit={submit}>
      <h1>{t('jobRequests.new')}</h1>
      <label>{t('jobForm.title')}<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      <label>{t('jobForm.sector')}<input value={sector} onChange={(e) => setSector(e.target.value)} /></label>
      <label>{t('jobForm.description')}<textarea value={description} onChange={(e) => setDescription(e.target.value)} /></label>
      <label>{t('jobForm.skills')}<input value={skills} onChange={(e) => setSkills(e.target.value)} /></label>

      <fieldset>
        <legend>{t('jobForm.languages')}</legend>
        {languages.map((l, i) => (
          <div key={i} className="lang-row">
            <input aria-label={`${t('jobForm.language')} ${i + 1}`} value={l.language} onChange={(e) => updateLanguage(i, { language: e.target.value })} />
            <select aria-label={`${t('jobForm.level')} ${i + 1}`} value={l.min_level} onChange={(e) => updateLanguage(i, { min_level: e.target.value as LanguageLevel })}>
              {LEVELS.map((lv) => <option key={lv} value={lv}>{t(`jobForm.level_${lv}`)}</option>)}
            </select>
            <button type="button" onClick={() => removeLanguage(i)}>{t('jobForm.removeLanguage')}</button>
          </div>
        ))}
        <button type="button" onClick={addLanguage}>{t('jobForm.addLanguage')}</button>
      </fieldset>

      <label>{t('jobForm.availability')}
        <select value={availability} onChange={(e) => setAvailability(e.target.value as Availability | '')}>
          <option value="">{t('jobForm.availabilityNone')}</option>
          {AVAILABILITIES.map((a) => <option key={a} value={a}>{t(`jobForm.availability_${a}`)}</option>)}
        </select>
      </label>
      <label className="check"><input type="checkbox" checked={nightShifts} onChange={(e) => setNightShifts(e.target.checked)} /> {t('jobForm.nightShifts')}</label>
      <label>{t('jobForm.prerequisites')}<input value={prerequisites} onChange={(e) => setPrerequisites(e.target.value)} /></label>

      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || !title || !sector}>{t('jobForm.submit')}</button>
    </form>
  )
}
