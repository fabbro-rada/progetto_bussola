import { useTranslation } from 'react-i18next'
import { useTextSize, type TextSize } from '../a11y/TextSize'

const SIZES: TextSize[] = ['normal', 'large', 'xlarge']

export function TextSizeControl() {
  const { t } = useTranslation()
  const { size, setSize } = useTextSize()
  return (
    <div className="text-size-control" role="group" aria-label={t('textSize.label')}>
      {SIZES.map((s) => (
        <button key={s} aria-pressed={size === s} onClick={() => setSize(s)}>
          {t(`textSize.${s}`)}
        </button>
      ))}
    </div>
  )
}
