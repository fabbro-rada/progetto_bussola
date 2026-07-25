import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { MatchResult } from '../../types'

function Card({ result }: { result: MatchResult }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const satisfied = result.requirements.filter((r) => r.satisfied).length
  const total = result.requirements.length
  return (
    <div className="match-card">
      <div className="match-head">
        <span className="pseudonym">{result.pseudonym_id}</span>
        <span className="badges">
          <span className="badge ok">✓ {t('match.constraintOk')}</span>
          <span className="fraction">{t('match.fraction', { n: satisfied, total })}</span>
          <button type="button" className="expand" onClick={() => setOpen((o) => !o)}>
            {open ? t('match.collapse') : t('match.expand')}
          </button>
        </span>
      </div>
      {open && (
        <div className="match-detail">
          <ul className="verdicts">
            {result.requirements.map((r, i) => (
              <li key={i}>
                <span className={r.satisfied ? 'ok' : 'no'}>{r.satisfied ? '✓' : '✗'}</span>{' '}
                <span className="requirement">{r.requirement}</span>
                {' — '}
                <em>{r.evidence ?? t('match.noEvidence')}</em>
              </li>
            ))}
          </ul>
          {result.gaps.length > 0 && (
            <div className="gaps">
              <strong>{t('match.gapsTitle')}</strong>
              <ul>
                {result.gaps.map((g, i) => (
                  <li key={i}>{g.requirement} → <em>{g.recommended_training}</em></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function MatchResults({ results }: { results: MatchResult[] }) {
  const { t } = useTranslation()
  if (results.length === 0) return <p>{t('detail.noResults')}</p>
  return (
    <div className="match-results">
      {results.map((r) => (
        <Card key={r.pseudonym_id} result={r} />
      ))}
    </div>
  )
}
