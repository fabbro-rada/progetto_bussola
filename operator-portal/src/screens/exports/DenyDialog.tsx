import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

export function DenyDialog({
  title,
  onConfirm,
  onCancel,
}: {
  title: string
  onConfirm: (reason: string) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const titleId = useId()
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className="modal">
        <h2 id={titleId}>{title}</h2>
        <label>{t('exports.denyReason')}
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <div className="modal-actions">
          <button type="button" onClick={onCancel}>{t('exports.cancel')}</button>
          <button type="button" className="primary" disabled={!reason.trim()} onClick={() => onConfirm(reason.trim())}>
            {t('exports.denyConfirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
