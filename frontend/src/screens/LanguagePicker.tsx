import { LANGUAGES } from '../i18n/languages'

// The picker itself is language-neutral: bilingual title + each endonym in its
// own script. No translated strings here (Global Constraints).
//
// The footer discharges the CC BY 4.0 attribution the French (siwis) voice
// requires (§3): creator, title, licence + link (as text — the kiosk is locked,
// so no navigable link), and the "voice modified" indication. It is
// language-neutral like the rest of this screen (shown before the language is
// chosen) and points to CREDITS.md for the full third-party credits.
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
      <footer className="picker-credits" lang="en">
        French voice: “SIWIS French Speech Synthesis Database” — CSTR, University
        of Edinburgh. Licensed CC BY 4.0
        (https://creativecommons.org/licenses/by/4.0/); voice modified. Full
        third-party credits: CREDITS.md.
      </footer>
    </div>
  )
}
