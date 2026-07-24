import { LANGUAGES } from '../i18n/languages'

// The picker itself is language-neutral: bilingual title + each endonym in its
// own script. No translated strings here (Global Constraints).
export function LanguagePicker({ onSelect }: { onSelect: (code: string) => void }) {
  return (
    <div className="language-picker">
      <h1 className="picker-title">Scegli la tua lingua · Choose your language</h1>
      <div className="language-grid">
        {LANGUAGES.map((l) => (
          <button
            key={l.code}
            className="language-tile"
            dir={l.dir}
            lang={l.code}
            onClick={() => onSelect(l.code)}
          >
            {l.name}
          </button>
        ))}
      </div>
    </div>
  )
}
