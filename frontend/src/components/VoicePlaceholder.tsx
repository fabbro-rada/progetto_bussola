import { useTranslation } from 'react-i18next'

// Voice is the next subsystem; this reserves the layout slot, inert for now.
export function VoicePlaceholder() {
  const { t } = useTranslation()
  return (
    <div className="voice-placeholder" aria-hidden="true">
      🎤 🔊 <em>{t('voice.placeholder')}</em>
    </div>
  )
}
