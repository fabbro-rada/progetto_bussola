import { useTranslation } from 'react-i18next'
import type { EvidenceGrade } from '../../types'

const ICON: Record<EvidenceGrade, string> = { certified: '✓', demonstrated: '◆', stated: '○' }

export function SkillBadge({ grade }: { grade: EvidenceGrade }) {
  const { t } = useTranslation()
  return (
    <span className={`ev-badge ev-${grade}`}>
      {ICON[grade]} {t(`pl.evidence_${grade}`)}
    </span>
  )
}
