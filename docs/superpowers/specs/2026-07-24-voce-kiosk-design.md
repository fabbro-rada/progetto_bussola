# Spec di design — Sottosistema 10: Voce del kiosk (lettura ad alta voce + dettatura)

**Progetto «Bussola»** · Sottosistema 10 · *Design di riferimento per il piano collegato* · 2026-07-24

---

## 0. Cos'è questo documento

Spec di design del decimo sottosistema, nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Estende l'UI kiosk della persona (S9) con lo **strato voce**: si conforma a `CLAUDE.md` §2 (linee rosse, ambito), §3 (locale, open source, budget zero, **prima il testo / voce come potenziamento / degrado elegante**, kiosk), §4 (volontarietà, non coercizione, **accessibilità e inclusione**), §7.1 (interazione vocale, ripiego voce↔testo), §8 (cinque lingue, arabo — voce con ripiego a testo), §9 (TDD, dati sintetici), §11 (codice inglese, stringhe UI esternalizzate i18n). Consuma l'**API voce di S8**: `POST /kiosk/voice/transcribe` (multipart `audio` + `language` → `{text}` | **503**) e `POST /kiosk/voice/synthesize` (`{text, language}` → WAV | **204**), entrambi con header `X-Kiosk-Token`.

## 1. Contesto e scopo

S9 ha costruito il kiosk **testo-first**: l'intero colloquio funziona in testo, con uno spazio riservato per la voce (`VoicePlaceholder`, inerte). Questo sottosistema **realizza la voce** — il potenziamento che, per §1/§4, evita che «metà delle persone resti di fatto esclusa»: chi ha bassa alfabetizzazione può **ascoltare** le domande e **parlare** invece di scrivere. Il testo resta sempre la base: la voce non sostituisce nulla, arricchisce e degrada con naturalezza.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Lettura ad alta voce (TTS)**: il testo della schermata corrente viene letto **automaticamente** quando appare (dopo lo sblocco audio del primo gesto), con «Riascolta» e un **muto** globale per-sessione. Consuma `synthesize`.
- **Dettatura (STT)**: **tocca-parla / tocca-stop** → trascrizione → il testo **compare nel campo** di risposta per revisione → la persona invia con «Avanti»/«Invia» (mai auto-invio). Consuma `transcribe`.
- **Barra voce contestuale** (`VoiceBar`), dentro ogni schermata sopra il campo: `[🎤 Parla]` (solo dove c'è un campo da riempire) · `[🔊 Ascolta]` (replay) · `[🔇 muto]`, con gli stati registra/trascrive.
- **Degrado elegante voce↔testo lato UI** (§3/§7.1): `transcribe` 503/rete o microfono negato/assente → si scrive; `synthesize` 204 → si legge soltanto; autoplay bloccato → resta il testo. Mai un blocco; «✕ Ferma» sempre in alto.

**Non-obiettivi (rimandati):**
- **Nuovi endpoint o modelli voce** — S7/S8 esistono; qui solo il client e l'UI.
- **Voce nel portale operatore** — la voce è solo per la persona.
- **Conferma vocale dei pulsanti** (dire «sì» per confermare il riepilogo) — i pulsanti conferma/correggi restano a tocco (già one-tap accessibili); «Parla» agisce solo sui **campi di testo**.
- **Voce araba in lettura (TTS)** — S7 non ha voce `ar` permissiva → `synthesize(ar)` = 204 → in arabo niente lettura, resta il testo (§8). La **dettatura** araba (Whisper) funziona. Aggiungere una voce `ar` è un follow-up backend.
- **Blindatura OS del kiosk / permessi a livello di sistema** → deployment.

## 3. Decisioni di design (con motivazione)

1. **La voce non tocca la macchina a stati; riempie campi e legge testi.** Il colloquio resta solo-testo (come S4/S8): STT scrive nel campo di risposta esistente, TTS legge `step.text`. *Perché §3:* disaccoppiamento; la voce è un potenziamento sopra un nucleo testuale che funziona da solo.

2. **Due hook + un client isolano le API del browser e di S8.** `useRecorder` incapsula `getUserMedia`/`MediaRecorder`; `useSpeech` incapsula la riproduzione `Audio`; `voiceClient` incapsula le due chiamate HTTP (fail-closed come `kioskClient`). *Perché §9:* le API del browser (assenti in jsdom) e la rete vivono dietro seam mockabili; i componenti restano testabili.

3. **Dettatura rivedibile, mai al buio (§5).** Tocca-parla/tocca-stop → la trascrizione **popola** il campo, la persona rilegge/corregge e invia esplicitamente. *Perché:* Whisper sbaglia (specie arabo/dialetti); ciò che entra nel colloquio/profilo dev'essere confermato dalla persona.

4. **Auto-lettura on-di-default con muto facile.** Alla comparsa di un nuovo `step`, il testo è letto automaticamente (se non muto); «Ascolta» rilegge on-demand (funziona anche a muto, richiesta esplicita); «🔇» disattiva l'auto-lettura e ferma la riproduzione. Preferenza per-sessione. *Perché §4:* chi legge poco sente subito la domanda senza sapere cosa premere; il muto copre privacy/rumore ambientale.

5. **Barra voce dentro la schermata, adattiva.** La `VoiceBar` vive nel corpo di ogni schermata sopra il campo (sostituisce `VoicePlaceholder`). `Parla` compare solo dove c'è un campo: Question/Refusal → bar completa; Summary/Clarification → Ascolta+muto sempre, Parla dopo «No, correggi»; Completed/Unauthorized/Unavailable → Ascolta+muto. *Perché:* «Parla» vicino a ciò che riempie; nessun comando inutile dove non serve.

6. **Sblocco audio al primo gesto + degrado all'autoplay.** L'audio si sblocca al primo tocco (lingua/consenso). Se l'autoplay resta bloccato, nessun errore: il testo c'è, «Ascolta» funziona dopo un tocco. *Perché §3:* mai un blocco per una policy del browser.

7. **Cattura WebM/Opus grezza, decodifica lato backend.** `MediaRecorder` produce WebM/Opus (default Chromium); il Blob è POSTato tale e quale a `transcribe` (faster-whisper decodifica via PyAV/ffmpeg). *Perché:* nessuna conversione audio nel browser. *Rischio:* mai verificato end-to-end (finora solo WAV) → §7.

8. **Degrado come nel resto del kiosk.** `transcribe`: 503/rete → risultato `'unavailable'` → nota «scrivi pure», campo resta; microfono negato/assente → «Parla» nascosto. `synthesize`: 204/rete → `null` → niente audio. Il client non solleva mai. *Perché §3/§7.1.*

## 4. Unità e confini

Nuove unità sotto `frontend/src/voice/` (+ integrazione nei componenti/screen S9):
- **`voiceClient`** — `transcribe(blob: Blob, language: string): Promise<{status:'ok'; text:string} | {status:'unavailable'}>`; `synthesize(text: string, language: string): Promise<Blob | null>`. Inietta `X-Kiosk-Token`; fetch avvolto (throw/503/rete → unavailable/null).
- **`useRecorder`** — hook: stato `idle|requesting|recording|transcribing|denied|unavailable`, `start()`, `stop()`, e un callback `onText(text)` quando la trascrizione riesce. Incapsula `getUserMedia`/`MediaRecorder` (iniettabili per i test).
- **`useSpeech`** — hook: `play(text, language)`, `stop()`, `muted`/`setMuted`; coda a-uno; rispetta il muto; `synthesize`→`null` = no-op. Incapsula `Audio`/object-URL.
- **`VoiceBar`** — componente presentazionale che compone i due hook: props `{ language, canDictate, onDictated(text), text }`. Sostituisce `VoicePlaceholder`.
- **Integrazione**: `AnswerPrompt`/`ConfirmCorrect` accettano il testo dettato nel loro campo; le screen passano `canDictate` e il `text` da leggere; `App` fornisce `language` e monta l'auto-lettura sul cambio di `step`. Il muto globale vive in un piccolo context (come `TextSize`).

Confine: dipende solo dal contratto HTTP voce di S8 e dalle API del browser dietro gli hook. Non tocca `kioskMachine` né il flusso del colloquio.

## 5. Flusso (voce in una interazione)

```
[nuovo step visualizzato] → useSpeech.play(step.text, language)  (se non muto; audio sbloccato al 1º gesto)
     synthesize {text, language} → Blob → riproduci | 204/null → niente audio (resta il testo)
[dettatura] tocca «Parla» → getUserMedia → MediaRecorder(rec) → «Stop»
     → Blob(webm) → transcribe(blob, language)
        ok {text} → popola il campo (revisione) → «Avanti»/«Invia» invia
        503/rete → «scrivi pure» (campo resta) ; permesso negato → «Parla» nascosto
[muto 🔇] → auto-lettura off + stop riproduzione ; [Ascolta] → replay on-demand
«✕ Ferma» sempre disponibile (S9)
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**. Vitest + @testing-library/react; `getUserMedia`/`MediaRecorder`/`Audio` mockati dietro gli hook, `voiceClient` con `fetch` mockato. Priorità sulla tenuta:
- **Dettatura**: registra→stop→trascrivi **popola il campo** e NON auto-invia; l'invio resta un gesto esplicito.
- **Degrado**: `transcribe` 503/rete → nota testo, campo resta; permesso microfono negato → «Parla» nascosto, il colloquio prosegue in testo; `synthesize` 204/null → nessun audio, nessun errore.
- **Auto-lettura**: parte al nuovo `step`; «🔇» la ferma/disattiva; «Ascolta» rilegge.
- **Client**: `transcribe`/`synthesize` inviano `X-Kiosk-Token`, il body/multipart corretto, e mappano 503/204/rete nei risultati tipizzati senza sollevare.
- **Integrazione reale** (opzionale/manuale, `requires_voice`): un **round-trip WebM reale** — registra→POST `transcribe` coi modelli reali — per validare la decodifica WebM/Opus; e un `synthesize` riprodotto.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| WebM/Opus non decodificato da faster-whisper (finora solo WAV) | round-trip reale come criterio d'accettazione opzionale + follow-up pre-pilota; se fallisse, registrare WAV via WebAudio o decodificare a monte |
| Autoplay bloccato dal browser | sblocco al primo gesto; degrado a testo + «Ascolta» manuale |
| Microfono negato/assente | stato `denied` → «Parla» nascosto, testo sempre attivo |
| Voce lenta blocca il colloquio | timeout già in S8 (503/204); l'UI mostra subito lo stato e ripiega |
| Lettura ad alta voce in spazio condiviso (privacy) | muto per-sessione ben visibile; testi di lavoro, non sensibili (§5) |
| Arabo senza voce TTS | 204 → niente lettura in arabo, resta il testo (§8); dettatura araba via Whisper OK |

## 8. Criteri di accettazione

- Unit (mock) verdi e deterministici: dettatura popola il campo senza auto-invio; degrado 503/permesso-negato/204 senza blocco; auto-lettura parte e si ferma col muto; il client inietta il token e mappa i codici.
- La `VoiceBar` sostituisce `VoicePlaceholder` e appare correttamente per tipo di schermata (Parla solo dove c'è un campo).
- Parità delle chiavi i18n con le nuove stringhe voce nei 5 cataloghi.
- `vitest`, typecheck, lint, build verdi. Solo dipendenze open source permissive (nessuna nuova dipendenza prevista — API del browser native).
- (Opzionale/manuale) round-trip WebM reale contro S8: la dettatura restituisce testo; `synthesize` produce audio riproducibile.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§4/§7.1/§8/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con lo strato voce del frontend (`voice/` client + hook, `VoiceBar`), le scelte (auto-lettura+muto, dettatura rivedibile, barra contestuale), lo sblocco audio, e i follow-up (round-trip WebM da validare; voce TTS araba assente).
- **Piano collegato:** scomposizione TDD, **TTS-prima** (client `synthesize` → `useSpeech` → auto-lettura/muto → `VoiceBar` lato ascolto), poi **STT** (client `transcribe` → `useRecorder` → dettatura nel campo → integrazione screen), infine round-trip reale opzionale.
