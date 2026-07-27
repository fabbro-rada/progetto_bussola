import type { TFunction } from 'i18next'
import type { ProfileFilters } from '../../types'

export function filterSummary(filters: ProfileFilters, t: TFunction): string {
  const parts: string[] = []
  if (filters.availability) parts.push(t(`pl.availability_${filters.availability}`))
  if (filters.language) parts.push(filters.language)
  if (filters.note) parts.push(t(`pl.note_${filters.note}`))
  if (filters.skill_query) parts.push(filters.skill_query)
  return parts.length > 0 ? parts.join(' · ') : t('exports.allProfiles')
}
