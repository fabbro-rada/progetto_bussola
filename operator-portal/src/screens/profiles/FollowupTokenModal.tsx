import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

function defaultCopy(text: string): Promise<void> {
  if (!navigator.clipboard) return Promise.reject(new Error('clipboard unavailable'))
  return navigator.clipboard.writeText(text)
}

// One-time follow-up token (S29): shown once for the operator to hand to the
// person, never re-persisted client-side. The caller clears its state on
// close, which is what actually makes the token disappear from memory —
// this component holds no copy of it beyond the `token` prop it was given.
export function FollowupTokenModal({
  token,
  subtitle,
  onClose,
  copy = defaultCopy,
}: {
  token: string
  subtitle: string
  onClose: () => void
  copy?: (text: string) => Promise<void>
}) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const titleId = useId()
  async function doCopy() {
    try {
      await copy(token)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className="modal">
        <h2 id={titleId}>{t('followups.tokenTitle')}</h2>
        <p className="modal-sub">{subtitle}</p>
        <p className="warn" role="alert">{t('followups.tokenWarning')}</p>
        <p>{t('followups.tokenInstructions')}</p>
        <div className="pw-row">
          <code className="pw">{token}</code>
          <button type="button" onClick={doCopy}>{copied ? t('followups.copied') : t('followups.copy')}</button>
        </div>
        <div className="modal-actions">
          <button type="button" className="primary" onClick={onClose}>{t('followups.close')}</button>
        </div>
      </div>
    </div>
  )
}
