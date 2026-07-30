import { LANGUAGES } from '../i18n/languages'

// The picker itself is language-neutral: bilingual title + each endonym in its
// own script. No translated strings here (Global Constraints).
//
// The footer discharges the CC BY 4.0 attribution the French (siwis) voice
// requires (§3): creator, title, licence + link (as text — the kiosk is locked,
// so no navigable link), and the "voice modified" indication. It is
// language-neutral like the rest of this screen (shown before the language is
// chosen) and points to CREDITS.md for the full third-party credits.
export function LanguagePicker({
  onSelect,
  onFollowupEntry,
}: {
  onSelect: (code: string) => void
  // Optional and additive (Task 6): omitted, the screen behaves exactly as
  // before (no link rendered) so the original first-interview entry point is
  // unchanged. Passed by App, it opens the follow-up token+language screen —
  // client-side only, no request fires from here.
  onFollowupEntry?: () => void
}) {
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
      {onFollowupEntry && (
        // Language-neutral like the rest of this screen (shown before a
        // language is chosen, same reasoning as the title above).
        <button type="button" className="followup-link" onClick={onFollowupEntry}>
          Ho un codice di follow-up · I have a follow-up code
        </button>
      )}
      {/* Explicit role: a <footer> nested in App's <main> loses its implicit
          contentinfo landmark (HTML-ARIA), so screen readers wouldn't expose it. */}
      <footer className="picker-credits" role="contentinfo" lang="en">
        French voice: “SIWIS French Speech Synthesis Database” — CSTR, University
        of Edinburgh. Licensed CC BY 4.0
        (https://creativecommons.org/licenses/by/4.0/); voice modified. Full
        third-party credits: CREDITS.md.
      </footer>
    </div>
  )
}
