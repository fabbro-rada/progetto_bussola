import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

function defaultCopy(text: string): Promise<void> {
  if (!navigator.clipboard) return Promise.reject(new Error('clipboard unavailable'))
  return navigator.clipboard.writeText(text)
}

// One-time interview start code (Task 9): shown once for the operator to hand
// to the person, never re-persisted client-side. Mirrors FollowupTokenModal —
// same one-time-secret shape, its own i18n namespace (`interviews.*`).
export function StartCodeModal({
  code,
  subtitle,
  onClose,
  copy = defaultCopy,
}: {
  code: string
  subtitle: string
  onClose: () => void
  copy?: (text: string) => Promise<void>
}) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const titleId = useId()
  async function doCopy() {
    try {
      await copy(code)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className="modal">
        <h2 id={titleId}>{t('interviews.startCodeTitle')}</h2>
        <p className="modal-sub">{subtitle}</p>
        <p className="warn" role="alert">{t('interviews.startCodeWarning')}</p>
        <p>{t('interviews.startCodeInstructions')}</p>
        <div className="pw-row">
          <code className="pw">{code}</code>
          <button type="button" onClick={doCopy}>{copied ? t('interviews.copied') : t('interviews.copy')}</button>
        </div>
        <div className="modal-actions">
          <button type="button" className="primary" onClick={onClose}>{t('interviews.close')}</button>
        </div>
      </div>
    </div>
  )
}
