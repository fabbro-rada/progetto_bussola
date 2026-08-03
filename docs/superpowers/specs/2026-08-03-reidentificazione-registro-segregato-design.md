# Re-identificazione via registro d'identità segregato — Design

**Data:** 2026-08-03 · **Sottosistema:** re-identificazione (pseudonimo ↔ persona)

## 1. Obiettivo e perché

Permettere a un **operatore** di ricollegare un profilo lavorativo pseudonimo alla **persona reale**, per due scopi concreti:
- **consegnare gli esiti del matching** (contattare le persone abbinate a una posizione);
- **emettere un codice di follow-up** alla persona giusta.

Mantenendo però il profilo lavorativo **minimo e pseudonimo**, e restringendo la **de-anonimizzazione al solo supervisore**, con audit completo.

## 2. Stato attuale (verificato nel codice)

- Lo pseudonimo è casuale (`data/pseudonym.py:15-17`), creato senza input della persona (all'avvio si sceglie solo la lingua).
- **Nessuna** tabella/campo collega lo pseudonimo a un'identità reale (schema `data/migrations/`, `profile/models.py`); il commento in `pseudonym.py:2-5` dichiara che «il registro pseudonimo↔persona vive fuori dal sistema».
- Lo **pseudonimo non è mai mostrato** a nessuno: la persona non riceve codici a fine colloquio (`Completed.tsx`), l'operatore vede solo pseudonimi (`MatchResults.tsx`, `ProfileSearch.tsx`).
- **Conseguenza:** non esiste alcun percorso di re-identificazione, nemmeno «esterno» (nessuno vede lo pseudonimo, quindi non è popolabile un registro esterno). La consegna dei match e il follow-up non hanno oggi un aggancio funzionante.

## 3. Modifiche al nucleo `CLAUDE.md` (§0 — approvate dall'utente il 2026-08-03)

Il design introduce, per scelta approvata, un **registro d'identità dentro il sistema ma fortemente segregato**. Questo cambia il modello concettuale del nucleo. Le modifiche vanno applicate come **primo passo** dell'implementazione (task 1), con il testo qui sotto.

### §5 — Modello del profilo (aggiunta)
Oggi dice: «un identificativo interno **pseudonimizzato**, separato dai dati anagrafici». Si **aggiunge** un paragrafo:

> **Registro d'identità segregato.** Il legame tra lo pseudonimo e la persona vive in un **registro separato** dal profilo lavorativo, che contiene **solo** lo pseudonimo e la **matricola** (il riferimento che la struttura già gestisce) — mai nome, anagrafica, reati, salute. Il registro è accessibile **soltanto al supervisore** per la de-anonimizzazione (§6) e **ogni accesso è tracciato** nel log di audit (§7.3). Il profilo lavorativo resta minimo e pseudonimo: chi lo consulta (operatore) **non** vede l'identità.

### §6 — Ruoli (modifiche)
- **Operatore:** oggi «Non recupera informazioni personali». Si precisa: l'operatore **avvia** i colloqui inserendo la **matricola** (crea il legame) ma **non può risolverlo**: scrive, non legge. Continua a lavorare solo su pseudonimi.
- **Supervisore:** oggi «Non è un validatore dei singoli dati». Si **aggiunge**: è l'**unica** autorità di **de-anonimizzazione** — l'unico ruolo che può risolvere `pseudonimo ↔ matricola`, per consegnare i match e per indirizzare i follow-up. Ogni risoluzione è a audit.

### §2 — Linee rosse (precisazione)
Si **aggiunge** che il registro d'identità è utilizzabile **solo** per orientamento/matching/follow-up e **mai** per sorveglianza, disciplina o valutazione; contiene **solo la matricola**; ogni accesso è tracciato e revisionabile dall'auditor.

### §7.3 — Audit (aggiunta)
La **creazione del legame** (all'avvio del colloquio) e ogni **de-anonimizzazione** sono eventi del log immutabile.

> Nota: `pseudonym.py` (docstring «register lives outside the system») va aggiornato di conseguenza; `STATO_TECNICO.md` riceve una riga di decisione.

## 4. Architettura

Quattro unità, con confini netti:

1. **Registro d'identità** (`identity/`): archivio segregato `pseudonimo ↔ matricola` + operazioni di scrittura (link) e lettura (resolve). Nessun'altra parte del sistema legge questo archivio se non attraverso il suo servizio.
2. **Provisioning del colloquio** (operatore): crea pseudonimo + profilo vuoto + legame + **codice di avvio monouso**; non restituisce lo pseudonimo.
3. **Avvio del kiosk da codice**: il kiosk consuma il codice di avvio (come già fa col token di follow-up) e parte sul profilo pre-creato.
4. **Risoluzione** (supervisore): de-anonimizza pseudonimo→matricola (match) e matricola→pseudonimo (follow-up), sempre a audit.

## 5. Modello dati

Nuovo schema `identity`, tabella:

```sql
CREATE TABLE identity.pseudonym_identity (
  pseudonym_id  text PRIMARY KEY REFERENCES profiles.work_profile(pseudonym_id),
  matricola     text NOT NULL UNIQUE,      -- una persona → un profilo
  created_at    timestamptz NOT NULL DEFAULT now(),
  created_by    text NOT NULL              -- username dell'operatore
);
CREATE INDEX ON identity.pseudonym_identity (matricola);  -- reverse lookup
```

- **Solo** `pseudonimo ↔ matricola` + metadati. `matricola` **UNIQUE**: una persona ha un solo profilo (gli aggiornamenti avvengono via follow-up). Provisioning con matricola già presente → errore chiaro («profilo già esistente, usa il follow-up»).
- Cifratura a riposo come il resto del DB; schema separato per segregazione (§3). Hardening opzionale: ruolo/grant DB distinto per `identity` (da valutare in implementazione).

## 6. Flussi

### 6.1 Creazione (operatore avvia)
1. Portale operatore → «Nuovo colloquio» → inserisce **matricola**.
2. `POST /interviews/provision` (permesso `PROVISION_INTERVIEW`): backend genera pseudonimo, crea profilo vuoto, inserisce il legame in `identity` (`created_by`=operatore, audit `identity_link_created`), genera un **codice di avvio monouso** (stessa macchina dei token di follow-up: hash memorizzato, scadenza) e restituisce **solo** `{ start_code }` — **mai** lo pseudonimo.
3. L'operatore consegna il codice alla persona; la persona sul kiosk inserisce il codice → **sceglie la lingua** → consenso → colloquio come oggi. Non vede né pseudonimo né matricola.

### 6.2 Avvio del kiosk (unificato con il follow-up)
- Il kiosk parte **sempre da un codice** (fine dell'avvio anonimo autonomo). Schermata «inserisci il codice» (generalizzazione di `FollowupEntry`).
- `POST /kiosk/interview/start` richiede `{ start_code, language }`; consuma il codice (monouso, atomico, fail-closed su invalido/scaduto/usato → 401), risolve lo pseudonimo e avvia il colloquio (primo colloquio) sul profilo pre-creato.
- Il follow-up resta il caso «codice che riprende un profilo esistente»: stessa schermata, stesso endpoint.

### 6.3 Risoluzione (supervisore de-anonimizza)
- **Matching:** l'operatore esegue il match → pseudonimi + punteggi → passa la lista al supervisore. Il supervisore (`POST /identity/resolve`, permesso `DEANONYMIZE`) risolve `pseudonimo → matricola`; ogni risoluzione → audit `identity_resolved`.
- **Follow-up:** l'operatore vuole ricontattare la persona X (matricola nota); il supervisore (`POST /identity/resolve-matricola`, `DEANONYMIZE`) risolve `matricola → pseudonimo` (audit); poi si emette il token di follow-up per quel profilo (flusso esistente `PROVISION_FOLLOWUP`).

## 7. API

| Endpoint | Ruolo/permesso | Body | Risposta | Audit |
|---|---|---|---|---|
| `POST /interviews/provision` | operatore · `PROVISION_INTERVIEW` | `{matricola}` | `{start_code}` (no pseudonimo) | `identity_link_created` |
| `POST /kiosk/interview/start` (mod.) | kiosk (device token) | `{start_code, language}` | `{sessionToken, step}` | — |
| `POST /identity/resolve` | supervisore · `DEANONYMIZE` | `{pseudonym_ids:[...]}` | `[{pseudonym_id, matricola}]` | `identity_resolved` (per pseudonimo) |
| `POST /identity/resolve-matricola` | supervisore · `DEANONYMIZE` | `{matricola}` | `{pseudonym_id}` o 404 | `identity_resolved` |

## 8. Ruoli/permessi (§6)

- Nuovo permesso **`DEANONYMIZE`** → **solo supervisore**.
- **`PROVISION_INTERVIEW`** (crea colloquio con matricola) → operatore (+ admin/supervisore se utile). L'operatore **non** ha `DEANONYMIZE`.
- Auditor: **non** ha `DEANONYMIZE`, ma vede gli eventi `identity_resolved`/`identity_link_created` nel log.

## 9. Portale operatore (UI)

- **Nuovo colloquio** (operatore): form matricola → mostra il codice di avvio una sola volta (riuso del modal token esistente). Non mostra lo pseudonimo.
- **Risoluzione** (supervisore): dalla schermata di matching (o profili), azione «de-anonimizza» sui pseudonimi selezionati → mostra le matricole (con avviso di scopo e audit). Visibile **solo** al ruolo supervisore.

## 10. Kiosk (UI)

- Schermata iniziale «inserisci il codice di avvio» prima del consenso (generalizza `FollowupEntry`); il resto del colloquio invariato. Degrado/accessibilità invariati (§4).

## 11. Sicurezza e privacy (trasversale)

- Archivio `identity` **separato** dal profilo; contiene **solo** matricola; cifrato a riposo (§3).
- De-anonimizzazione **solo** supervisore (`DEANONYMIZE`); **ogni** accesso a audit immutabile (§7.3); accesso **vincolato allo scopo** (§2).
- Il provisioning **non** espone lo pseudonimo all'operatore → l'operatore non può costruire una mappa pseudonimo↔persona.
- Codice di avvio: monouso, con scadenza, hash memorizzato (mai in chiaro), fail-closed (come il follow-up).

## 12. Testing (TDD; sicurezza per prima, §9)

1. **Accesso ristretto:** operatore/admin/auditor che chiamano `/identity/resolve*` → **403**; solo supervisore → 200.
2. **Nessuna fuga:** `POST /interviews/provision` **non** contiene mai lo pseudonimo nella risposta.
3. **Audit:** ogni `resolve` e ogni `provision` producono l'evento d'audit atteso (attore, pseudonimo, direzione).
4. **Segregazione:** il profilo (`work_profile`) continua a non contenere identità; il registro `identity` contiene solo matricola.
5. **Codice di avvio:** monouso (secondo uso → 401), scaduto → 401.
6. **Unicità matricola:** provisioning duplicato → errore chiaro, nessun secondo profilo.
7. **Reverse lookup:** matricola→pseudonimo corretto; matricola sconosciuta → 404.
8. Flussi end-to-end: provision → start(kiosk) → colloquio; match → resolve; follow-up (resolve matricola → issue token).

## 13. Migrazione / compatibilità

- Nuova migrazione per lo schema `identity`.
- I profili **anonimi già esistenti** (senza legame) restano **non risolvibili** — nessun collegamento retroattivo (fuori scope). Per il pilota (avvio nuovo) è accettabile.
- Il kiosk passa da avvio anonimo a avvio-da-codice: aggiornare gli smoke/e2e di conseguenza.

## 14. Fuori scope

- Collegamento retroattivo dei profili anonimi esistenti.
- Dati anagrafici liberi nel registro (solo matricola).
- Ruolo DB dedicato per lo schema `identity` (hardening opzionale, valutabile in seguito).
