import { useId } from 'react'
import { useTranslation } from 'react-i18next'

export function ConfirmDialog({
  message,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  message: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const messageId = useId()
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={messageId}>
      <div className="modal">
        <p id={messageId}>{message}</p>
        <div className="modal-actions">
          <button type="button" onClick={onCancel}>{t('operators.cancel')}</button>
          <button type="button" className="primary" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
