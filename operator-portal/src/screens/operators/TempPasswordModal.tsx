import { useState } from 'react'
import { useTranslation } from 'react-i18next'

function defaultCopy(text: string): Promise<void> {
  return navigator.clipboard?.writeText(text) ?? Promise.resolve()
}

export function TempPasswordModal({
  password,
  subtitle,
  onClose,
  copy = defaultCopy,
}: {
  password: string
  subtitle: string
  onClose: () => void
  copy?: (text: string) => Promise<void>
}) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  async function doCopy() {
    await copy(password)
    setCopied(true)
  }
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={t('operators.tempPasswordTitle')}>
      <div className="modal">
        <h2>{t('operators.tempPasswordTitle')}</h2>
        <p className="modal-sub">{subtitle}</p>
        <p className="warn" role="alert">{t('operators.tempPasswordWarning')}</p>
        <div className="pw-row">
          <code className="pw">{password}</code>
          <button type="button" onClick={doCopy}>{copied ? t('operators.copied') : t('operators.copy')}</button>
        </div>
        <div className="modal-actions">
          <button type="button" className="primary" onClick={onClose}>{t('operators.close')}</button>
        </div>
      </div>
    </div>
  )
}
