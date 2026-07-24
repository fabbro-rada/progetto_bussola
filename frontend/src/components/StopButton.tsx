import { useTranslation } from 'react-i18next'

export function StopButton({ onStop }: { onStop: () => void }) {
  const { t } = useTranslation()
  return (
    <button className="stop-button" onClick={onStop}>
      ✕ {t('stop.label')}
    </button>
  )
}
