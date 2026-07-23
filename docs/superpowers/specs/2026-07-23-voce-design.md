# Spec di design — Sottosistema 7: Voce (STT + TTS)

**Progetto «Bussola»** · Sottosistema 7 · *Design di riferimento per il piano collegato* · 2026-07-23

---

## 0. Cos'è questo documento

Spec di design del settimo sottosistema, nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §3 (locale, open source **permissivo**, budget nullo; **prima il testo, la voce come potenziamento, degrado elegante**), §4 (accessibilità/inclusione: lettura vocale, bassa alfabetizzazione), §7.1 (interazione vocale + ripiego elegante voce↔testo), §8 (cinque lingue; arabo come obiettivo con ripiego a testo se la resa non è adeguata), §9 (TDD, dati sintetici). Riusa la scelta dei modelli già registrata in `STATO_TECNICO.md` §4.2 (STT = faster-whisper) e §4.3 (TTS = Piper).

## 1. Contesto e scopo

Realizza i **servizi backend di voce**: trascrizione (Speech-to-Text) delle risposte parlate e sintesi (Text-to-Speech) di domande/riepiloghi, in modo che chi ha **bassa alfabetizzazione** o preferisce la voce possa **parlare invece di scrivere** e **ascoltare invece di leggere** (§4/§7.1). Girano **su CPU** (nessuna contesa con l'LLM su GPU, `STATO_TECNICO` §5). Sono **servizi**, non un layer HTTP: il kiosk/browser (cattura microfono, riproduzione audio, trasporto rivolto alla persona con la sua sicurezza) e il wiring nel loop del colloquio sono del **frontend (S8)**.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **STT**: `SpeechToText.transcribe(audio, lingua) -> Transcription` (faster-whisper, int8 su CPU), con la lingua scelta all'onboarding come hint.
- **TTS**: `TextToSpeech.synthesize(testo, lingua) -> bytes | None` (Piper, voce per lingua), WAV o `None` se non c'è voce per quella lingua.
- **Degrado elegante** (§3/§7.1): voce non disponibile/lenta/assente → contratto che fa **ripiegare il chiamante sul testo**, senza mai bloccare.
- **Multilingua** (§8): STT per tutte e 5 le lingue incluso l'arabo; TTS con **voci a licenza permissiva**; arabo-TTS **solo-testo di default** finché non validato sul pilota.

**Non-obiettivi (rimandati):**
- **HTTP / cattura audio nel browser / kiosk** → S8 (frontend).
- **Wiring nel loop del colloquio** (chi chiama transcribe/synthesize e quando) → S8.
- **VAD / streaming / barge-in / diarizzazione** → Fase 2 se servirà.
- **Cloning vocale / voci di qualità superiore** (es. XTTS): escluso — licenza del modello **non commerciale**, incompatibile con §3 (`STATO_TECNICO` §4.3).

## 3. Decisioni di design (con motivazione)

1. **Servizi backend, non HTTP.** Deliverable = classi `SpeechToText`/`TextToSpeech` con un contratto di degrado chiaro; nessun endpoint. *Perché:* il trasporto rivolto alla **persona detenuta** (non un operatore autenticato) e la blindatura kiosk appartengono a S8 (stesso confine del motore-colloquio S4, che è backend-only). Mantiene la voce **disaccoppiata** dal colloquio.

2. **STT = faster-whisper, int8 su CPU** (`STATO_TECNICO` §4.2). Modello caricato una volta (costoso) e riusato. Default `large-v3-turbo` (equilibrio qualità/velocità), **configurabile** (`large-v3` per l'arabo di massima qualità; `small`/`medium` per più reattività sul kiosk). Si passa la **lingua scelta** come hint (niente auto-detect ambiguo). *Perché §3/§8:* miglior STT open, copre l'arabo, gira su CPU lasciando la GPU all'LLM.

3. **TTS = Piper, voce per lingua** (`STATO_TECNICO` §4.3). `synthesize -> bytes(WAV) | None`. *Perché §3:* leggero, CPU-friendly, permissivo; l'alternativa di qualità superiore (XTTS) è non-commerciale → esclusa.

4. **Degrado elegante come contratto esplicito** (§3/§7.1). **STT** giù/errore/timeout/modello assente → solleva `VoiceUnavailable` → il chiamante scrive. **TTS** assente/errore/lingua senza voce → ritorna **`None`** (non un'eccezione: l'assenza di audio è un ripiego normale) → il chiamante legge. La voce è **puro potenziamento**: il testo funziona sempre.

5. **Licenze delle voci Piper vetted per-voce** (§3). Si selezionano **solo voci a licenza permissiva** (MIT/CC0/CC-BY/public-domain), una per lingua; le licenze non-permissive (non-commerciale/copyleft incompatibile) sono **escluse**, coerentemente col precedente S1 (`it_core_news_lg` CC BY-NC-SA escluso). La licenza di ogni voce usata è annotata in `STATO_TECNICO`.

6. **Arabo: obiettivo con ripiego a testo, di default** (§8). L'arabo STT è pieno (Whisper). L'arabo **TTS** parte come **solo-testo** (`synthesize("...", "ar")` → `None`) finché una voce araba **adeguata e permissiva** non è validata sul pilota. *Perché:* l'onestà del §8 — non diamo per buona una resa che potrebbe non esserlo; il colloquio non ne risente.

7. **Validazione empirica sul pilota** (§9/§10). Come per l'LLM (matching/colloquio), la qualità reale si **misura**, non si assume: test d'integrazione con i modelli reali + smoke per lingua; la decisione «arabo-TTS attivabile» è subordinata alla validazione. *Perché:* i servizi sono wrapper **sostituibili** — se una lingua rende male, si sale di modello o si passa a testo senza riscrivere.

## 4. Unità e confini

Nuovo package **`bussola.voice`**:
- `config.py` — tunables da env: modello STT + device/compute, cartella modelli, mappa `lingua → voce Piper` (arabo assente di default), soglie/timeout.
- `errors.py` — `VoiceUnavailable(Exception)`.
- `models.py` — `Transcription(text: str, language: str)` (Pydantic).
- `stt.py` — `SpeechToText`: carica il modello una volta; `transcribe(audio: bytes, language: str) -> Transcription`; su fallimento → `VoiceUnavailable`.
- `tts.py` — `TextToSpeech`: carica le voci; `synthesize(text: str, language: str) -> bytes | None`.

Confine: `bussola.voice` dipende solo dai suoi modelli + librerie STT/TTS. **Non** conosce colloquio, HTTP, DB. Espone i due servizi. Il consumatore (S8) decide quando/come chiamarli e gestisce il ripiego a testo secondo il contratto §3.4.

## 5. Contratto (una interazione vocale, lato consumatore S8)

```
persona parla → S8 cattura l'audio → SpeechToText.transcribe(audio, lingua)
     VoiceUnavailable → S8 mostra l'input di testo (la persona scrive)
     Transcription(text) → il text entra nel colloquio (submit)
sistema produce una domanda/riepilogo (testo) → TextToSpeech.synthesize(testo, lingua)
     None → S8 mostra solo il testo (la persona legge)
     bytes(WAV) → S8 riproduce l'audio (e mostra comunque il testo)
```

Il testo è **sempre** presente; la voce si aggiunge quando c'è.

## 6. Strategia di test (§9)

TDD; **solo dati sintetici** (frasi di lavoro sintetiche).
- **Unit con engine finto** (deterministico, nessun modello reale, veloci): il **contratto di degrado** — STT che fallisce → `VoiceUnavailable`; TTS senza voce per la lingua o in errore → `None`; hint di lingua propagato al motore; l'arabo-TTS ritorna `None` di default.
- **Integrazione coi modelli reali** (`requires_voice`, skip se i modelli non sono presenti): **round-trip** auto-contenuto — `TextToSpeech.synthesize(frase nota, lingua)` → WAV → `SpeechToText.transcribe(quel WAV, lingua)` → asserisco che la trascrizione contiene le **parole chiave** (robusto alle piccole differenze). Almeno **it** ed **en**; arabo come obiettivo (marcato, non bloccante). Nessun file audio esterno.
- Priorità: la **tenuta del degrado** (mai un blocco), la propagazione della lingua, il ripiego dell'arabo.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| STT lento sul kiosk (CPU) | modello configurabile (`small`/`medium`); il degrado a testo evita blocchi; misura sul pilota |
| Arabo STT su dialetti | Whisper è il miglior open; gli errori emergono nel *riepiloga-e-conferma* (§5 colloquio) e la persona corregge |
| Qualità/licenza voce araba TTS | arabo-TTS = solo-testo di default finché non validato + permissivo (§6) |
| Voce Piper a licenza non permissiva | vetting per-voce; solo permissive (§3), annotate in STATO_TECNICO |
| Modelli assenti in test/CI | unit con engine finto (sempre); integrazione reale skippata se i modelli mancano |
| Voce che blocca il colloquio | contratto: `VoiceUnavailable`→testo, `None`→testo; il testo funziona sempre |

## 8. Criteri di accettazione

- Unit (engine finto) verdi e deterministici: `VoiceUnavailable` su STT giù; `None` su TTS assente/errore/arabo-default; hint di lingua propagato.
- Con i modelli reali (`requires_voice`): round-trip TTS→STT su it/en con parole chiave riconosciute; nessun blocco in nessun percorso di degrado.
- Solo voci Piper a **licenza permissiva** (verificate al momento dell'aggiunta), annotate.
- `pytest`, `ruff`, `ruff format --check`, `mypy` verdi. Dipendenze nuove permissive (`faster-whisper` MIT, `piper-tts` MIT).

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§3/§4/§7.1/§8/§9). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con i servizi voce, i modelli/voci effettivi e le loro **licenze**, il default STT, il contratto di degrado e l'esito della **validazione empirica** della voce.
- **Piano collegato:** scomposizione TDD (contratto di degrado + multilingua prima; poi integrazione reale round-trip). I modelli/voci si scaricano una volta con uno script (come `serve-llm.sh`), percorsi da env, binari non versionati.
