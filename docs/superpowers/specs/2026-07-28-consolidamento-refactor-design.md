# Spec di design — Sottosistema 22: Consolidamento (refactor a comportamento invariato)

**Progetto «Bussola»** · Sottosistema 22 (chore di consolidamento del debito tecnico §14) · *Design di riferimento per il piano collegato* · 2026-07-28

---

## 0. Cos'è questo documento

Spec di design di un **consolidamento a comportamento invariato**: quattro cleanup di duplicazione accumulata durante S15–S21, raccomandati dalle review finali e tracciati in `STATO_TECNICO.md` §14. **Non è una nuova funzionalità**: nessun cambiamento osservabile per gli utenti, nessuna modifica al contratto HTTP, nessuna modifica al nucleo. La **rete di sicurezza è la suite di test esistente** (backend 303, frontend 127): dopo il refactor deve restare **verde e invariata** (salvo test aggiunti per le nuove astrazioni). Si conforma a `CLAUDE.md` §3 (open source, solo azioni previste), §9 (nessun indebolimento delle garanzie; TDD; le astrazioni nuove hanno i loro test), §11 (codice inglese). **Nessuna linea rossa toccata** (nessun cambio di sicurezza, RBAC, dati o comportamento).

## 1. Contesto e scopo

Costruendo i quattro pannelli del portale (metriche, attività, config, audit) sono emerse duplicazioni identiche: la lista delle 5 lingue in 3 punti backend, il boilerplate fetch-on-mount in 3 pannelli, la formattazione timestamp in 2 punti, e un commento ormai stale in `nav.ts`. Questo consolidamento le unifica **senza cambiare comportamento**, riducendo il rischio di drift futuro (es. aggiungere una lingua e aggiornarne solo una copia).

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **`SUPPORTED_LANGUAGES` unica fonte (backend).** Una costante condivisa in un modulo neutro; le 3 copie attuali (`guardrails/refusal.py`, `guardrails/pii.py`, `system/service.py`) la riusano. Stessi 5 valori, stesso ordine.
- **Hook `useFetchOnMount` (frontend).** Un hook che centralizza il pattern fetch-al-mount + degrado (`useApiError` + messaggio i18n + stato loading/error) usato identico da `MetricsPanel`, `OperatorActivityPanel`, `SystemConfigPanel`.
- **Util `formatTimestamp` (frontend).** Una funzione che produce **esattamente** l'output attuale (`iso.replace('T',' ').slice(0,16)`), riusata da `AuditLog` e `OperatorActivityPanel`.
- **Commento `nav.ts` aggiornato.** Il commento non descrive più «placeholder disabilitati» (ora tutte le voci sono `built`); il flag `built?` **resta** (utile per future sezioni non ancora pronte).

**Non-obiettivi (esclusi / rimandati):**
- **Cambiamenti di comportamento.** Nessuno. In particolare `formatTimestamp` **non** aggiunge l'indicatore di fuso orario (era una proposta di *miglioramento*, non di dedup): resta un follow-up §14 per non alterare l'output.
- **Rimozione del flag `built?`** (scelta approvata: tenerlo).
- **Redactor PII condiviso/cached** (scope più grande, cross-cutting): rimandato a un intervento focalizzato dedicato (§14).
- **`ruff format --check` nel gate** e riformattazione dei file pre-esistenti: rimandato (modifica al gate CI, separata).
- **Formatter di date con TZ, hook generici oltre i 3 pannelli, ecc.**: fuori scope.

## 3. Decisioni di design (con motivazione)

1. **Refactor a comportamento invariato, verificato dai test esistenti (§9).** Ogni modifica preserva il comportamento osservabile; le suite backend/frontend restano verdi **senza modifiche alle asserzioni esistenti**. Le nuove astrazioni (`useFetchOnMount`, `formatTimestamp`) ottengono **test focalizzati propri**. *Perché §9:* «non indebolire le garanzie»; il refactor si giustifica solo se dimostrabilmente neutro.

2. **`SUPPORTED_LANGUAGES` in un modulo neutro, non in `guardrails`.** Un nuovo `bussola/languages.py` (dipendenza-free) è la fonte unica; `guardrails/refusal.py` e `system/service.py` la importano; `guardrails/pii.py` usa `list(SUPPORTED_LANGUAGES)` (Presidio vuole una lista). *Perché:* evitare che `system` dipenda da `guardrails` (accoppiamento innaturale); un modulo neutro è la casa giusta per una costante trasversale. I nomi pubblici esistenti (`refusal.SUPPORTED_LANGUAGES`) restano risolvibili (re-export via import).

3. **`useFetchOnMount(fetcher, onOk)` centralizza il pattern, i pannelli restano sottili.** L'hook incapsula `useApiError`, la mappatura errori i18n (`errors.forbidden`/`errors.generic`), lo stato `data/error` e la guardia unmount; ogni pannello passa `() => client.getX()` + un selettore `(r) => r.<campo>`. *Perché:* il boilerplate era identico in 3 punti; centralizzarlo riduce il drift e i pannelli diventano dichiarativi. Il degrado (401→login, 403→messaggio, error→messaggio, loading gated `!error`) è preservato **identico**.

4. **`formatTimestamp` a output identico (dedup puro).** Stessa trasformazione stringa di oggi; **nessun** cambiamento di resa. *Perché §9/invarianza:* un dedup non deve introdurre differenze osservabili; l'eventuale indicatore TZ è un miglioramento separato (§14).

5. **`built?` mantenuto, solo commento corretto.** *Perché (scelta approvata):* il meccanismo resta utile per future sezioni non pronte; il churn è minimo e nessun test viene rimosso.

## 4. Unità e confini

**Backend** (`backend/src/bussola/`):
- **`languages.py`** (nuovo) — `SUPPORTED_LANGUAGES: tuple[str, ...] = ("it", "en", "fr", "es", "ar")`.
- **`guardrails/refusal.py`**, **`guardrails/pii.py`**, **`system/service.py`** (modifica) — importano la costante condivisa; `pii.py` usa `list(...)`.

**Frontend** (`operator-portal/src/`):
- **`hooks/useFetchOnMount.ts`** (nuovo) — l'hook generico.
- **`screens/metrics/MetricsPanel.tsx`**, **`screens/activity/OperatorActivityPanel.tsx`**, **`screens/system/SystemConfigPanel.tsx`** (modifica) — usano l'hook.
- **`util/formatTimestamp.ts`** (o `screens/…/format.ts`; nuovo) — la util.
- **`screens/audit/AuditLog.tsx`**, **`screens/activity/OperatorActivityPanel.tsx`** (modifica) — usano `formatTimestamp`.
- **`rbac/nav.ts`** (modifica) — commento aggiornato.

Confine: nessun cambiamento al contratto HTTP, ai tipi pubblici, all'RBAC o alla resa. Solo struttura interna.

## 5. Interfacce delle nuove astrazioni

- **`SUPPORTED_LANGUAGES: tuple[str, ...]`** = `("it","en","fr","es","ar")`.
- **`useFetchOnMount<R, T>(fetcher: () => Promise<R>, onOk: (r) => T): { data: T | null; error: string }`** — dove `R` è una result-union con `{ status: 'ok' | 'unauthorized' | 'forbidden' | 'error', ... }`; su `ok` chiama `onOk` e setta `data`; su `unauthorized` invoca `useApiError` (redirect); su `forbidden`/`error` setta `error` col messaggio i18n; guardia unmount `active`.
- **`formatTimestamp(iso: string): string`** = `iso.replace('T', ' ').slice(0, 16)` (identico all'attuale).

## 6. Strategia di test (§9)

- **Backend**: le suite esistenti restano verdi **senza modifiche**. Aggiungere un test che `bussola.languages.SUPPORTED_LANGUAGES == ("it","en","fr","es","ar")` e che i tre consumatori la referenzino (import risolvibili); i test di guardrail (refusal/pii) e `system` già esistenti coprono l'uso a valle.
- **Frontend**: i test dei 3 pannelli e di `AuditLog` restano verdi **senza modifiche alle asserzioni** (dimostrano l'invarianza). Aggiungere test focalizzati per `useFetchOnMount` (ok→data; forbidden→messaggio; unauthorized→redirect; loading gated) e `formatTimestamp` (ISO → «YYYY-MM-DD HH:MM»).
- **Regola**: se un test esistente deve cambiare per far passare il refactor, **fermarsi**: non è più a comportamento invariato — segnalare.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Il refactor cambia comportamento di nascosto | i test esistenti restano invariati e verdi; qualunque asserzione da modificare è un segnale di stop |
| `useFetchOnMount` altera il degrado (401/403/error/loading) | l'hook replica esattamente la logica dei pannelli; i test dei pannelli (incl. 403/401/error/empty) lo verificano invariati |
| `formatTimestamp` cambia la resa | output byte-identico all'attuale (nessun TZ ora) |
| Import ciclico / accoppiamento con la costante lingue | modulo neutro `languages.py` dependency-free; re-export mantiene i nomi pubblici |
| Rimozione involontaria di copertura | nessun test rimosso (il flag `built?` resta) |

## 8. Criteri di accettazione

- Le suite backend (pytest/ruff/mypy) e frontend (vitest/typecheck/lint/build) sono **verdi**; nessuna asserzione esistente modificata; aggiunti solo i test delle nuove astrazioni.
- Una sola definizione di `SUPPORTED_LANGUAGES`; i 3 pannelli usano `useFetchOnMount`; i 2 timestamp usano `formatTimestamp`; commento `nav.ts` aggiornato.
- Nessun cambiamento a contratto HTTP, RBAC, tipi pubblici o resa. `frontend/` (kiosk) intatto. Nessuna nuova dipendenza.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§3/§9/§11). **Nessuna modifica al nucleo**; nessun comportamento cambiato.
- **`STATO_TECNICO.md`**: aggiornare §14 marcando risolti i follow-up consolidati (SUPPORTED_LANGUAGES, hook fetch, commento nav) e precisando quelli rimandati (redactor PII cached, formatter TZ, `ruff format` nel gate); riga §15 per il consolidamento.
- **Piano collegato:** scomposizione TDD (backend: `languages.py` + dedup + test; frontend: `formatTimestamp` + applicazione + `nav.ts`; poi `useFetchOnMount` + refactor dei 3 pannelli).
