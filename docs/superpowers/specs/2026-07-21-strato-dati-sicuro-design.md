# Spec di design — Sottosistema 2: Strato dati sicuro (PostgreSQL)

**Progetto «Bussola»** · Sottosistema 2 · *Design di riferimento per il piano collegato* · 2026-07-21

---

## 0. Cos'è questo documento

Spec di design del secondo sottosistema, nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* costruiamo e *perché*, non il codice passo-passo (quello vive nel piano). Deriva da `CLAUDE.md` §2/§5/§6/§7.3/§9 (funzionale) e da `STATO_TECNICO.md` §6 (tecnico), che aggiorna dove le decisioni di brainstorming lo raffinano.

## 1. Contesto e scopo

Realizza lo **strato dati sicuro**: dove e come vivono i **profili lavorativi** e il **registro di audit**, con la segregazione, la minimizzazione e l'immutabilità richieste dal nucleo. Poggia sul Sottosistema 1 (il modello `WorkProfile` e `sanitize_profile`). È fondamento per l'estrazione/persistenza del colloquio (Sott. 4) e per il portale operatore (Sott. 6).

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- Schema PostgreSQL segregato + **ruoli DB a privilegio minimo** (owner / app / auditor).
- **Persistenza dei profili** per pseudonimo, con **filtro PII applicato al salvataggio**.
- **Ciclo di vita dello pseudonimo** (generazione di un identificativo opaco, creazione/recupero del profilo).
- **Registro di audit** append-only con **hash-chain** anti-manomissione + API di append e di verifica.
- **Migrazioni SQL** versionate e riproducibili; **docker-compose** per Postgres locale.

**Non-obiettivi (rimandati, con destinazione):**
- **Account operatore, autenticazione, RBAC** → nuovo sottosistema **«Auth & operatori»** (prima del portale, Sott. 6). Qui l'audit prevede il campo `actor`, che verrà popolato da quel sottosistema.
- **Log delle conversazioni** → Sottosistema 4 (colloquio). Gli schemi nascono già separati per accoglierli.
- **Indici di ricerca per il matching** (GIN su JSONB) → Sottosistema 6.
- **Cifratura a riposo** = **LUKS full-disk**, passo di *deployment* (documentato), non codice. Nessun `pgcrypto`: senza dati identità non c'è nulla di sensibile da cifrare a colonna.

## 3. Decisioni di design (con motivazione)

1. **Nessun dato di identità nel sistema.** Il legame pseudonimo↔persona vive **fuori** dal sistema (registro dell'istituto). *Perché:* lettura più forte di «privacy by design» e minimizzazione (§4/§5): niente anagrafica ⇒ niente da cifrare, segregare o far trapelare. Elimina del tutto la tabella di mappatura cifrata ipotizzata in `STATO_TECNICO.md` §6.

2. **Due attori diversi *in natura* (vedi §5-attori).** L'**operatore** è un principal autenticato (account di staff, ruolo) ed è l'`actor` dell'audit. La **persona detenuta** non ha account né identità nel sistema: è identificata **solo dallo pseudonimo** di sessione, provisionata da un operatore. *Perché:* riflette la realtà del kiosk e tiene le linee rosse (l'auditor vede «operatore X → pseudonimo Y», mai una persona).

3. **psycopg3 + migrazioni SQL.** Driver psycopg3 + repository sottile e tipizzato; migrazioni come file `.sql` ordinati. *Perché:* il DDL di sicurezza (schemi, ruoli, `GRANT`/`REVOKE`, append-only, hash-chain) resta in SQL puro, massimamente trasparente e revisionabile; poche dipendenze. **Runner di migrazione:** minimale e interno (tabella `schema_migrations` + applicazione dei file in ordine), per non introdurre una dipendenza da verificare (dopo il caso di licenza del Sott. 1). Alternativa possibile: `yoyo-migrations`, previa verifica di licenza.

4. **Ruoli DB coarse + RBAC applicativo.** `bussola_owner` (DDL/migrazioni), `bussola_app` (RW su `profiles`, **solo-INSERT** su `audit`), `bussola_auditor` (**solo-SELECT** su `audit`). *Perché:* l'append-only e la sola-lettura dell'auditor sono **imposti dal DB**, non dal «buon comportamento» dell'app; le distinzioni operatore/supervisore/amministratore sono autorizzazione applicativa (RBAC nel sottosistema Auth). Pratico con pooling e single-box.

5. **Profilo come JSONB.** `profiles.work_profile(pseudonym_id PK, profile JSONB, created_at, updated_at)`. *Perché:* il `WorkProfile` è già validato da Pydantic (unica fonte di verità), e JSONB è flessibile per il matching futuro senza normalizzazione prematura. Lettura: `WorkProfile.model_validate(jsonb)` (ri-validazione).

6. **Filtro PII al salvataggio, fail-closed.** Il repository applica **`sanitize_profile` prima di persistere** (§7.3: «prima di mostrare o salvare») e **gestisce esplicitamente** il possibile `ValidationError` (contratto fail-closed del Sott. 1). *Perché:* il modello non decide da solo cosa esporre; e il salvataggio non produce mai un profilo schema-invalido. Chiude il carry-forward del Sottosistema 1.

7. **Audit append-only + hash-chain.** `audit.audit_log(id, occurred_at, actor, action, target_pseudonym, details JSONB, prev_hash, record_hash)`. Append-only: `UPDATE`/`DELETE` **revocati** al ruolo app **+ trigger** che li vieta a tutti tranne owner. Hash-chain: `record_hash = sha256(canonical(campi) ‖ prev_hash)`; una funzione **verifica** la catena e segnala la prima rottura. *Perché:* accountability e garanzia concreta contro il riuso improprio (§6 Auditor); cintura (grant) + bretelle (trigger + hash).

8. **Pseudonimo generato dal sistema.** Identificativo opaco, non indovinabile, unico (es. token casuale URL-safe), conforme al vincolo del modello (`min_length≥1, max_length≤64`). *Perché:* garantisce unicità e opacità; l'operatore lo trascrive nel registro esterno.

## 4. Unità e confini

Nuovo package **`bussola.data`**, a responsabilità singola:

- `config.py` — DSN e parametri di connessione da variabili d'ambiente (per ruolo: owner/app/auditor).
- `connection.py` — helper di connessione psycopg3 (context manager; pool opzionale).
- `migrations/` — file `.sql` ordinati (schemi+ruoli, profili, audit).
- `migrate.py` — runner minimale (applica le migrazioni non ancora registrate).
- `pseudonym.py` — `generate_pseudonym() -> str`.
- `profiles.py` — `ProfileRepository`: `save(profile)` (sanitizza+persiste), `get(pseudonym_id)`, `create_new() -> pseudonym`.
- `audit.py` — `append_audit(...)`, `verify_audit_chain() -> VerificationResult`.

Confine: `bussola.data` dipende da `bussola.profile` (modello) e `bussola.guardrails` (`sanitize_profile`); espone repository/funzioni; non conosce nulla del portale o del colloquio.

## 5. Modello dati e ruoli

**Schemi:** `profiles`, `audit` (separati; futuro `conversations` per il Sott. 4).

**Ruoli / grant (imposti dal DB):**

| Ruolo | profiles | audit |
|---|---|---|
| `bussola_owner` | ALL (DDL) | ALL (DDL) |
| `bussola_app` | SELECT/INSERT/UPDATE | **INSERT + SELECT** (no UPDATE/DELETE) |
| `bussola_auditor` | — (nessun accesso) | **SELECT** |

- `audit.audit_log`: `UPDATE`/`DELETE` vietati a `app` (revocati) e a tutti via **trigger** (solo `owner` per manutenzione straordinaria).

### 5-attori — chi è chi

- **Operatore:** autenticato (account di staff: username, hash password, ruolo — nel sottosistema Auth). È l'`actor` dell'audit.
- **Persona detenuta:** nessun account, nessuna identità nel sistema; solo `pseudonym_id` di sessione, provisionato da un operatore; il legame alla persona è nel registro **esterno**.

## 6. Strategia di test (sicurezza prima)

Postgres via docker-compose; DB di test con migrazioni applicate; **solo dati sintetici**. Ordine di priorità:

1. **Append-only imposto dal DB:** `app` può `INSERT` sull'audit ma **non** `UPDATE`/`DELETE` (permission denied / errore del trigger).
2. **Segregazione dei ruoli:** `auditor` legge l'audit ma **non** i profili; `app` non può alterare l'audit.
3. **Hash-chain:** una manomissione di un record è **rilevata** dalla verifica della catena.
4. **Filtro al salvataggio:** `save` applica `sanitize_profile`; PII non persiste; fail-closed gestito.
5. **Round-trip del profilo:** `save`→`get` restituisce un `WorkProfile` equivalente e valido.
6. **Migrazioni:** applicazione idempotente e riproducibile da zero.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Runner di migrazioni fatto in casa fragile | Minimale e testato; ordine deterministico; registrazione in `schema_migrations` |
| Trigger append-only aggirabile | Doppia difesa: `REVOKE` dei permessi **e** trigger; owner separato dall'app |
| Segreti (password ruoli) in chiaro | `.env` gitignorato; `.env.example` versionato; mai segreti nel repo |
| JSONB non ottimizzato per la ricerca | Accettabile ora; indici GIN nel Sott. 6 (matching) |
| Test dipendono da Postgres attivo | docker-compose + fixture che migra un DB di test e ripulisce tra i test |

## 8. Criteri di accettazione

- I ruoli e i grant sono imposti dal DB: `app` non può modificare/cancellare l'audit; `auditor` non vede i profili.
- L'hash-chain rileva ogni manomissione.
- `save` sanitizza e non persiste mai PII; il fail-closed è gestito; `save`→`get` fa round-trip.
- Migrazioni riproducibili da zero; `docker-compose up` porta un Postgres pronto.
- `pytest`, `ruff`, `mypy` verdi; solo dati sintetici.

## 9. Relazione con gli altri documenti e roadmap

- **`CLAUDE.md`** (nucleo protetto): questa spec vi si conforma (§2/§5/§6/§7.3). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: aggiornato §6 (niente mappatura/identità; ruoli coarse; ciclo pseudonimo).
- **Roadmap:** si **inserisce** un sottosistema **«Auth & operatori»** (account, autenticazione, RBAC) prima del portale operatore. La numerazione successiva scala di uno.
- **Piano collegato:** la scomposizione eseguibile in TDD di questo design.
