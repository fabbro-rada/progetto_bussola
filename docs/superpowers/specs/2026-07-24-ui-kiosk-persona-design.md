# Spec di design — Sottosistema 9: UI kiosk della persona (text-first)

**Progetto «Bussola»** · Sottosistema 9 · *Design di riferimento per il piano collegato* · 2026-07-24

---

## 0. Cos'è questo documento

Spec di design del nono sottosistema — **il primo frontend** — nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (linee rosse, ambito), §3 (locale, open source, budget zero, **prima il testo / degrado elegante**, prevenzione abusi, postazione bloccata), §4 (volontarietà e consenso, non coercizione, accessibilità e inclusione), §7.1 (onboarding e consenso, scelta lingua, colloquio a tappe, riepilogo e conferma, chiarimento incongruenze, ambito bloccato, accessibilità, kiosk), §8 (cinque lingue, arabo RTL), §9 (TDD, solo dati sintetici), §11 (codice in inglese, stringhe utente esternalizzate/i18n). Consuma l'**API kiosk (S8)** — `POST /kiosk/interview/start|submit` e (rimandati) `/kiosk/voice/*` — su STATO_TECNICO §2/§6 (**single-box, solo localhost, secure-context, no TLS**).

## 1. Contesto e scopo

Realizza l'**interfaccia rivolta alla persona detenuta**: l'esperienza che conduce il colloquio dall'inizio (consenso, scelta lingua) alla fine, consumando turno-per-turno l'API S8. Finora l'intero backend di Fase 1 (S1–S8) è pronto ma **senza volto**: questo sottosistema è il volto, per la persona. La persona **non fa login** (l'autenticazione è a livello di dispositivo, S8); l'esperienza deve funzionare per chi ha bassa alfabetizzazione, non parla italiano, o è in una condizione di stress.

Questo sottosistema è **text-first**: realizza l'intero flusso in modalità **testo**. La **voce** (cattura microfono + riproduzione TTS, degrado voce↔testo lato UI) è il **sottosistema successivo**, che si innesta su questa base. Questa scomposizione incarna il §3 — «prima il testo, la voce come potenziamento» — al livello dei sottosistemi, e mantiene trattabile il primo frontend.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Flusso completo della persona in testo**: `scelta lingua → consenso informato → colloquio turno-per-turno → fine`, guidato dall'API S8 (`start`/`submit`).
- **Rendering per `step.kind`**: `question`, `summary` (riepilogo con conferma/correzione a due pulsanti), `clarification` (stesso pattern), `refusal` (rifiuto gentile in-ambito), `unavailable` (degrado), `completed` (fine).
- **Multilingua + RTL** (§8): 5 lingue nella loro scrittura; l'arabo ribalta l'interfaccia (`dir=rtl`). Stringhe della UI esternalizzate (§11); il contenuto del colloquio è già localizzato dal backend.
- **Accessibilità** (§4): default grande e ad alto contrasto, controllo dimensione testo per la sessione, focus visibile, aree touch generose, etichette ARIA, testo semplificato.
- **Comando «Ferma» sempre disponibile** (§4/§7.1): interrompe e azzera, in ogni momento.
- **Degrado elegante end-to-end** (§3): `unavailable`/`404`/`401` non bloccano mai; il testo funziona sempre.
- **Sicurezza kiosk lato client**: `X-Kiosk-Token` (build-time) su ogni chiamata; nessuna identità della persona.

**Non-obiettivi (rimandati):**
- **Voce** — cattura microfono, riproduzione TTS, degrado voce↔testo lato UI, uso di `/kiosk/voice/*` → **sottosistema successivo** (i controlli voce qui sono un placeholder disabilitato).
- **Blindatura OS del kiosk** (Chromium `--kiosk`, utente Linux dedicato, blocco input) → deployment.
- **Ripresa di un colloquio interrotto a metà** → Fase 2 (le sezioni confermate sono già persistite da S4; qui un reload riparte da capo).
- **UI portale operatore** → sottosistema separato.
- **«Opzioni rapide» a scelta nel colloquio** (§7.1): il motore colloquio (S4) produce domande a testo libero; le opzioni strutturate sarebbero un'evoluzione futura del motore. *Limitazione nota, non modifica del nucleo* (vedi §9).

## 3. Decisioni di design (con motivazione)

1. **Macchina a stati di schermi, non routing di URL.** Un riduttore guida lo schermo attivo (`lingua|consenso|colloquio|fine`); dentro *colloquio* lo schermo deriva dal `step.kind` dell'API. *Perché §7.1/kiosk:* è il sistema a condurre, non c'è navigazione libera; nessuna URL da manomettere sulla postazione bloccata.

2. **Una domanda alla volta (schermata focalizzata).** Ogni turno mostra **solo** la domanda corrente, grande e centrata, con un unico campo di risposta e «Avanti». *Perché §7.1:* «domande brevi», «meno ansia», un solo compito per volta; ideale per bassa alfabetizzazione. Il *riepilogo di fine sezione* copre l'esigenza di rivedere ciò che si è detto, senza ricostruire lato UI uno storico che l'API non restituisce.

3. **Riepilogo e conferma a due pulsanti.** Sullo `step.kind==="summary"`: il testo riassuntivo dell'API + **«✓ Sì, è corretto»** e **«✏️ No, correggi»** (che apre il campo di testo). *Perché §5/§4:* confermare diventa un solo gesto, senza scrivere — decisivo per chi ha bassa alfabetizzazione; la correzione resta testo libero. La conferma invia un testo di conferma a `submit`; la correzione invia il testo digitato. Lo **stesso pattern** serve lo `step.kind==="clarification"` (chiarimento incongruenze, §7.1) — senza giudicare.

4. **Il degrado è resa, non errore.** `step.kind==="unavailable"` (LLM giù, arriva come 200 da S8) → schermo di attesa gentile con invito a riscrivere; `404` (sessione scaduta) → ritorno all'inizio con garbo; `401` (token errato) → schermo «postazione non autorizzata» (problema di configurazione, non della persona). *Perché §3:* il testo non si blocca mai; il ripiego è naturale.

5. **Stato in memoria, niente persistenza lato client.** Lo stato dell'app (token di sessione, schermo, preferenze) vive in memoria; nessun `localStorage`/cookie. *Perché §3/§4/privacy:* un reload perde la sessione in corso (privacy-safe); le sezioni confermate sono già persistite da S4; la ripresa a metà è Fase 2. Il token di sessione opaco di S8 non tocca l'URL.

6. **i18n esternalizzato + RTL alla radice.** Cataloghi di stringhe per it/en/fr/es/ar (§11); nessuna stringa hard-coded. La scelta lingua imposta catalogo **e** `dir` (`rtl` per l'arabo) sull'elemento radice. *Perché §8/§4:* la lingua è la prima barriera; l'arabo richiede il ribaltamento dell'intera interfaccia. Il **contenuto** del colloquio è già nella lingua scelta (passata a `start`), quindi la UI localizza solo la propria cornice.

7. **Accessibilità come default, con una sola regolazione.** Base grande e ad alto contrasto; un controllo dimensione testo (Normale/Grande/Molto grande) valido per la sessione, via variabili CSS su root; contrasto alto e fisso (una scelta in meno per la persona). Focus visibile, ruoli/etichette ARIA, aree touch generose, «Ferma» sempre raggiungibile. *Perché §4:* dignità e inclusione, senza sovraccaricare di scelte.

8. **Client API isolato con token build-time.** Un solo modulo incapsula le chiamate S8 e inietta `X-Kiosk-Token` da una variabile d'ambiente Vite (`VITE_KIOSK_TOKEN`), inclusa nel bundle servito solo su localhost. *Perché §3/S8:* token di dispositivo pre-condiviso adatto al pilota single-box; nessun endpoint extra; rotazione = rebuild. I componenti non conoscono `fetch`, solo il client.

9. **Voce come placeholder disabilitato.** I controlli voce (Parla/Ascolta) sono presenti ma inattivi e marcati «prossima fase». *Perché §3/scomposizione:* riservano lo spazio nel layout senza introdurre qui la complessità audio del browser (mock di `getUserMedia`/`MediaRecorder`) — che vive nel sottosistema voce.

## 4. Unità e confini

Cartella nuova `frontend/` (Vite + React + TS). Unità con responsabilità singola:

- **`src/api/kioskClient`** — chiamate a S8 (`startInterview(language)`, `submitAnswer(token, answer)`); inietta `X-Kiosk-Token`; mappa gli esiti HTTP in un risultato tipizzato (`ok | session-expired | unauthorized`). Non conosce React. **Non** usa `/kiosk/voice/*` (rimandato).
- **`src/state/kioskMachine`** — riduttore dello schermo attivo e transizioni (`lingua→consenso→colloquio→fine`; dentro colloquio, derivazione da `step.kind`); azione `stop` che azzera. Puro, testabile in isolamento.
- **`src/i18n`** — cataloghi it/en/fr/es/ar + selezione lingua e direzione (`dir`). Chiave→stringa; nessuna stringa nei componenti.
- **`src/a11y`** — contesto dimensione testo (variabili CSS) e utilità di accessibilità.
- **`src/screens/`** — un componente per schermo/stato: `LanguagePicker`, `Consent`, `Question`, `Summary` (conferma/correggi), `Clarification`, `Refusal`, `Unavailable`, `Completed`. Componenti di presentazione, guidati dallo stato.
- **`src/components/`** — primitivi condivisi: `StopButton`, `TextSizeControl`, `VoicePlaceholder`, campo di risposta, pulsanti grandi.
- **`src/App`** — compone macchina + client + i18n + a11y; monta «Ferma» sempre.

Confine: `frontend/` dipende **solo** dal contratto HTTP di S8; non conosce il DB, i modelli, gli altri sottosistemi. Nessun accoppiamento col portale operatore.

## 5. Flusso (una sessione della persona)

```
[apertura] LanguagePicker → sceglie lingua L (imposta catalogo + dir)
      → Consent (testo semplificato in L): «Ho capito, iniziamo» | «Non ora»
POST /kiosk/interview/start {language: L}   [header X-Kiosk-Token]
      → {session_token, step}  → render per step.kind
loop del colloquio:
  step.kind == "question"      → Question: campo di testo → «Avanti»
  step.kind == "summary"       → Summary: «✓ Sì, è corretto» | «✏️ No, correggi»
  step.kind == "clarification" → Clarification: stesso pattern a pulsanti
  step.kind == "refusal"       → Refusal: avviso gentile, riporta al tema
  step.kind == "unavailable"   → Unavailable: attesa gentile, invito a riscrivere
  step.kind == "completed"     → Completed: schermo di fine
  (qualunque azione) POST /kiosk/interview/submit {session_token, answer} → {step}
      401 → «postazione non autorizzata» ·  404 → sessione scaduta, torna a lingua
«✕ Ferma» (sempre montato) → azzera lo stato, torna a LanguagePicker
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**. Vitest + React Testing Library; `kioskClient` sostituito da un fake deterministico (nessun backend nei test unitari). Priorità sulla **tenuta**:
- **Rendering per `step.kind`**: ogni kind rende lo schermo corretto; `summary`/`clarification` mostrano i due pulsanti; `refusal` mostra il rifiuto **restando in-ambito**.
- **Degrado, mai un blocco**: `unavailable` (200) → schermo di attesa con input ancora disponibile; `404` → ritorno all'inizio; `401` → schermo postazione non autorizzata.
- **Conferma/correggi**: «Sì, è corretto» invia il testo di conferma a `submit`; «Correggi» apre il campo e invia il testo digitato.
- **«Ferma»**: azzera davvero lo stato e riporta a `lingua` da qualunque schermo.
- **i18n/RTL**: cambio lingua cambia le stringhe della cornice; l'arabo imposta `dir=rtl`.
- **Accessibilità**: il controllo dimensione testo applica le variabili; focus/etichette presenti.
- **Client**: `startInterview`/`submitAnswer` inviano `X-Kiosk-Token`; mappano 200/401/404 nel risultato tipizzato.

Smoke end-to-end contro l'API S8 reale: **opzionale/manuale**, fuori dalla suite unitaria.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| La persona resta bloccata se il backend è giù | `unavailable`/`404`/`401` resi come schermi gentili; testo sempre attivo; «Ferma» sempre |
| Interfaccia illeggibile per bassa alfabetizzazione/ipovisione | default grande + alto contrasto; controllo dimensione testo; una domanda alla volta |
| Arabo non ribaltato correttamente | `dir=rtl` alla radice + test dedicato; ripiego comunque leggibile |
| Stringhe fuori dai cataloghi (regressione i18n) | nessuna stringa hard-coded; test che verifica il cambio lingua |
| Token kiosk esposto | bundle servito solo su localhost (secure-context); token di dispositivo, non identità |
| Reload perde il colloquio | privacy-safe by design; sezioni confermate già persistite (S4); ripresa = Fase 2 |
| Confusione tra conferma e correzione | due pulsanti distinti; la conferma non richiede di scrivere |

## 8. Criteri di accettazione

- Unit (fake client) verdi e deterministici: rendering corretto per ogni `step.kind`; degrado (`unavailable`/`404`/`401`) senza blocco; conferma/correggi inviano il testo giusto; «Ferma» azzera; i18n cambia le stringhe; arabo `dir=rtl`; controllo dimensione testo applica le variabili; il client inietta `X-Kiosk-Token`.
- Il flusso completo `lingua → consenso → colloquio → fine` è percorribile con il fake client.
- `vitest`, lint e type-check (TS) verdi. Solo dipendenze open source permissive.
- (Opzionale/manuale) smoke contro l'API S8 reale su localhost: un breve colloquio in testo.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§4/§7.1/§8/§9/§11). **Nessuna modifica al nucleo.** *Nota di trasparenza (§0):* il §7.1 cita «opzioni rapide»; il motore colloquio (S4) produce domande a testo libero, quindi questa UI realizza «domande brevi / il sistema conduce» ma **non** opzioni strutturate a scelta. Non è una modifica del nucleo — è una limitazione dell'implementazione attuale, tracciata come possibile evoluzione futura del motore colloquio. Se in futuro si volesse renderla nativa, si seguirà la governance §0.
- **`STATO_TECNICO.md`**: da aggiornare con la cartella `frontend/` (Vite+React+TS), il `kioskClient`, la macchina a stati degli schermi, i18n/RTL, l'accessibilità con controllo dimensione testo, il token kiosk build-time (`VITE_KIOSK_TOKEN`), e la scomposizione text-first / voce-successiva.
- **Piano collegato:** scomposizione TDD (scaffold Vite+React+TS + gate di test; poi `kioskClient` + macchina a stati; poi i18n/RTL + accessibilità; poi gli schermi uno alla volta; infine composizione del flusso e «Ferma»).
