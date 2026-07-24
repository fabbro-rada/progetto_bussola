# Spec di design — Sottosistema 8: API rivolta alla persona (kiosk)

**Progetto «Bussola»** · Sottosistema 8 · *Design di riferimento per il piano collegato* · 2026-07-24

---

## 0. Cos'è questo documento

Spec di design dell'ottavo sottosistema, nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (linee rosse, ambito), §3 (locale, budget zero, **prima il testo/degrado elegante**, prevenzione abusi, postazione bloccata), §4 (volontarietà: interrompibile in ogni momento; accessibilità), §7.1 (colloquio a tappe, voce, ripiego voce↔testo, kiosk), §9 (TDD, dati sintetici). Riusa S3 (`HttpxLlmClient`, `ScopeGuard`), S4 (`Interview` orchestratore turno-per-turno), S1/S2 (`ProfileRepository`, `PiiRedactor`, `append_audit`), S7 (`SpeechToText`, `TextToSpeech`). Poggia su STATO_TECNICO §2/§6 (**topologia single-box, solo localhost**).

## 1. Contesto e scopo

Realizza il **layer HTTP mancante rivolto alla persona detenuta**: guida il **colloquio turno-per-turno** e offre le **utilità vocali** (trascrivi/sintetizza), così che il **kiosk (UI, sottosistema successivo)** possa condurre l'esperienza. Finora colloquio (S4) e voce (S7) sono servizi backend senza endpoint: questo sottosistema li espone, con una **sessione e una sicurezza adatte al kiosk** (la persona non fa login).

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Colloquio via HTTP**: `start(language)` → primo `Step`; `submit(answer)` → `Step` successivo (turno-per-turno, deterministico, guidato dall'app — §7.1).
- **Voce via HTTP**: `transcribe(audio, language)` → testo; `synthesize(text, language)` → audio; **con timeout** e segnali di degrado chiari.
- **Sessione kiosk**: stato server-side del colloquio (l'`Interview` è stateful in-memory), legato a un token di sessione opaco; TTL e ripulitura.
- **Sicurezza kiosk**: token di dispositivo pre-condiviso; nessuna identità della persona; bind `localhost` (§3/STATO_TECNICO §6).
- **Degrado elegante end-to-end** (§3/§7.1): voce non disponibile/lenta → segnale che fa ripiegare il kiosk sul testo; il colloquio degrada già di suo (Step `unavailable`).

**Non-obiettivi (rimandati):**
- **UI kiosk React** (cattura microfono, riproduzione, accessibilità, RTL, comando «ferma» come UI, blindatura schermo) → sottosistema successivo.
- **Blindatura OS del kiosk** (Chromium `--kiosk`, utente Linux dedicato) → deployment.
- **Condivisione sessioni multi-worker / multi-postazione simultanea** → Fase 2 (il pilota è una postazione, un processo).
- **TLS interno / topologia LAN** → evoluzione di produzione (vedi §3.6).
- **UI portale operatore** → sottosistema separato (gli endpoint operatore esistono già).

## 3. Decisioni di design (con motivazione)

1. **Endpoint sottili sopra `Interview` (S4).** `Interview.start()/submit(answer)` sono già la macchina a stati turno-per-turno; gli endpoint si limitano a esporli. *Perché §7.1:* «il sistema conduce» resta nell'orchestratore, prevedibile e già testato; l'HTTP non aggiunge logica di flusso.

2. **Sessione server-side in un registry in-memory.** `Interview` è **stateful** (tiene `InterviewSession`): un registry modulo-level mappa `session_token` (opaco, `secrets`) → istanza `Interview`. `start` crea la sessione; `submit` la ritrova. **TTL** + sweep delle sessioni abbandonate. *Perché §S4/§4:* una postazione simultanea; la persona può interrompere in ogni momento (le sezioni confermate restano persistite da S4). *Nota:* single-box, un processo uvicorn; non multi-worker (Fase 2).

3. **Voce separata dal colloquio.** Il colloquio resta **solo-testo** (come S4); `transcribe`/`synthesize` sono utilità generiche. Il kiosk orchestra: STT(risposta) → `submit(testo)` → TTS(`step.text`). *Perché:* disaccoppiamento (come S7); niente audio dentro la macchina a stati.

4. **Voce avvolta da timeout → chiude il follow-up di S7.** Le chiamate STT/TTS (sincrone, S7) sono eseguite con un **timeout** (`BUSSOLA_VOICE_TIMEOUT`, default es. 10s): endpoint async + `asyncio.wait_for(run_in_executor(...))`. Alla scadenza (o su `VoiceUnavailable`/`None`) si restituisce un **segnale di degrado**. *Perché §3/§7.1:* realizza qui la metà **«voce lenta → testo»** che S7 aveva esplicitamente lasciato a questo layer. *(Caveat pilota: il thread scaduto termina da solo; accettabile su single-box.)*

5. **Degrado come segnali HTTP chiari.** `transcribe`: `VoiceUnavailable`/timeout → **503** («usa il testo»). `synthesize`: `None`/timeout → **204** («niente audio, mostra il testo»). Il colloquio: Step `unavailable` (S4) su LLM giù, esposto tale e quale. *Perché §3:* il kiosk ripiega sul testo senza mai bloccarsi; il testo funziona sempre.

6. **Sicurezza kiosk: token di dispositivo + localhost (single-box).** `require_kiosk`: header `X-Kiosk-Token` confrontato in **tempo costante** con `BUSSOLA_KIOSK_TOKEN` (env) → assente/errato = **401**. Bind `127.0.0.1` (nessun dato in rete, §3/§6); **nessun TLS** necessario (localhost è *secure context* → il microfono del browser funziona senza certificati). La persona **non** ha identità/login. *Perché §3:* prevenzione dell'abuso al livello giusto senza appesantire la persona. *Evoluzione (fuori scope):* su topologia LAN servirebbe TLS interno (dati in transito §6 + secure-context per il microfono) e il token diventerebbe il controllo primario.

7. **Audit degli eventi di colloquio.** L'`Interview` audita già le sezioni confermate (hook S4); qui l'`actor` è `"kiosk"` (non un operatore). Le chiamate voce non sono auditate (interazione pseudonima, nessun attore-operatore). *Perché §7.3:* accountability dove ha senso, senza tracciare la persona.

## 4. Unità e confini

- **`bussola.api.kiosk.session`** — `InterviewRegistry`: `create(interview) -> token`, `get(token) -> Interview | None`, `discard(token)`, sweep TTL. Token opaco.
- **`bussola.api.kiosk.deps`** — `require_kiosk` (device-token dependency); costruzione di un `Interview` (factory che inietta `HttpxLlmClient`/`ScopeGuard`/`ProfileRepository`/`PiiRedactor`/audit) e dei servizi voce (`SpeechToText`/`TextToSpeech`); config timeout.
- **`bussola.api.routers.kiosk_interview`** — `POST /kiosk/interview/start`, `POST /kiosk/interview/submit`.
- **`bussola.api.routers.kiosk_voice`** — `POST /kiosk/voice/transcribe`, `POST /kiosk/voice/synthesize`.
- `create_app()` monta i due router.

Confine: dipende da `bussola.{interview,voice,guardrails,llm,data,profile}`. Non conosce la UI. Espone gli endpoint kiosk. Nessun accoppiamento col portale operatore.

## 5. Flusso (una interazione kiosk)

```
[la UI kiosk invia sempre X-Kiosk-Token; assente/errato → 401]
POST /kiosk/interview/start {language}
     → crea Interview (pseudonimo via ProfileRepository), registry[token]=Interview
     → {session_token, step(question)}
(voce, opzionale) POST /kiosk/voice/transcribe (audio, language)  [timeout]
     ok → {text}   |  VoiceUnavailable/timeout → 503 (scrivi a mano)
POST /kiosk/interview/submit {session_token, answer}
     → registry[token].submit(answer) → {step}  (question|summary|clarification|refusal|unavailable|completed)
     sessione ignota/scaduta → 404
(voce, opzionale) POST /kiosk/voice/synthesize {text: step.text, language}  [timeout]
     bytes(WAV) → riproduci  |  None/timeout → 204 (leggi soltanto)
... ripeti submit fino a step.kind == "completed"
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**. Via FastAPI `TestClient` (+ override delle dipendenze per iniettare fake).
- **Sicurezza kiosk**: nessun/errato `X-Kiosk-Token` → 401 su ogni endpoint kiosk.
- **Colloquio (LLM finto)**: `start` → `session_token` + primo `step`; `submit` guida i turni (question→summary→…); sessione ignota → 404; il flusso di degrado dell'`Interview` (`unavailable`) passa inalterato.
- **Sessione**: due `start` danno token distinti; `discard`/TTL rimuove; `submit` su token scaduto → 404.
- **Voce (engine finto)**: `transcribe` ok → `{text}`; `VoiceUnavailable` → 503; **timeout** (engine finto lento) → 503; `synthesize` bytes → audio; `None` → 204; **timeout** → 204.
- **Integrazione reale** opzionale (`requires_llm`+`requires_voice`): un colloquio breve via HTTP con Qwen2.5 + un round-trip voce; skip se assenti.

Priorità: la tenuta della **sicurezza kiosk** (401), del **degrado** (503/204, mai un blocco), e della **sessione** (isolamento/scadenza).

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Client non autorizzato guida colloqui | `require_kiosk` (token dispositivo, tempo costante) + bind localhost |
| Voce lenta blocca il colloquio | timeout su transcribe/synthesize → 503/204 → ripiego a testo (chiude il follow-up S7) |
| Sessioni abbandonate accumulano memoria | TTL + sweep; una postazione simultanea |
| Perdita stato colloquio a metà | le sezioni confermate sono già persistite (S4); ripresa a metà = Fase 2 |
| Fuga PII nei testi mostrati | l'`Interview` applica già il filtro PII sui testi generati (S4) prima di restituirli |
| Multi-worker romperebbe il registry in-memory | pilota single-process; multi-worker = Fase 2 (documentato) |

## 8. Criteri di accettazione

- Unit (fake) verdi e deterministici: 401 senza token; `start`/`submit` guidano un colloquio; 404 su sessione ignota; voce → `{text}`/audio, degrado 503/204 incl. timeout.
- Con Qwen2.5 + voce reali (opzionale): un colloquio breve end-to-end via HTTP; round-trip voce; nessun blocco nei percorsi di degrado.
- `pytest`, `ruff`, `ruff format --check`, `mypy` verdi. Nessuna nuova dipendenza.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§4/§7.1/§9). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con gli endpoint kiosk, il registry di sessione, il token di dispositivo, il **timeout voce (chiusura del follow-up S7)**, e la conferma della topologia single-box/localhost (bind 127.0.0.1, no TLS, microfono via secure-context).
- **Piano collegato:** scomposizione TDD (sessione + device-token prima; poi endpoint colloquio; poi endpoint voce con timeout; infine integrazione reale opzionale).
