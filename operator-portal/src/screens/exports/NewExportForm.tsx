import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { Availability, OperationalNoteCategory, ProfileFilters } from '../../types'

const AVAILABILITIES: Availability[] = ['full_time', 'part_time', 'flexible']
const NOTES: OperationalNoteCategory[] = [
  'needs_language_support', 'needs_literacy_support', 'limited_availability', 'prefers_team_work', 'prefers_solo_work',
]

export function NewExportForm({
  onSubmit,
  onCancel,
  busy,
  error,
}: {
  onSubmit: (filters: ProfileFilters, reason: string) => void
  onCancel: () => void
  busy: boolean
  error: string
}) {
  const { t } = useTranslation()
  const [availability, setAvailability] = useState<Availability | ''>('')
  const [language, setLanguage] = useState('')
  const [note, setNote] = useState<OperationalNoteCategory | ''>('')
  const [skillQuery, setSkillQuery] = useState('')
  const [reason, setReason] = useState('')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!reason.trim()) return
    const filters: ProfileFilters = {}
    if (availability) filters.availability = availability
    if (language.trim()) filters.language = language.trim()
    if (note) filters.note = note
    if (skillQuery.trim()) filters.skill_query = skillQuery.trim()
    onSubmit(filters, reason.trim())
  }

  return (
    <form className="op-create" onSubmit={submit}>
      <h2>{t('exports.createTitle')}</h2>
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
      <label>{t('exports.reason')}<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="op-create-actions">
        <button type="button" onClick={onCancel}>{t('exports.cancel')}</button>
        <button type="submit" disabled={busy || !reason.trim()}>{t('exports.create')}</button>
      </div>
    </form>
  )
}
