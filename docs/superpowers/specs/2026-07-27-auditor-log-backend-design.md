# Spec di design — Sottosistema 18: Vista del log di audit (Auditor) — Backend

**Progetto «Bussola»** · Sottosistema 18 (ruolo Auditor · lettura del log di audit — **parte backend**) · *Design di riferimento per il piano collegato* · 2026-07-27

---

## 0. Cos'è questo documento

Spec di design della **parte backend** della vista del log di audit per il ruolo **Auditor** (§6). L'auditor «garantisce il corretto uso»: accede **in sola lettura** al log per verificare **chi ha fatto cosa e quando** — è «la garanzia concreta contro il riuso improprio dei dati» (§6/§2). Il sottosistema è decomposto in **backend** (questo documento: endpoint di lettura + verifica della catena) e **frontend** (spec successiva: il visore). Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*. Si conforma a `CLAUDE.md` §2 (accountability contro il riuso improprio; nessuna sorveglianza sulle persone detenute — il log traccia le **azioni degli operatori**), §3 (locale, open source, solo azioni previste, fail-closed), §6 (ruolo **Auditor**, **sola lettura**, «non modifica nulla e non partecipa all'operatività», privilegio minimo; il server resta l'autorità), §7.3 (**registro di audit immutabile**, tamper-evidence hash-chain), §9 (TDD, dati sintetici), §11 (codice inglese).

Il registro di audit esiste già (S2): tabella `audit.audit_log` **append-only** (trigger anti-mutazione) e **hash-chained** (tamper-evident), popolata da ogni sottosistema (auth, colloquio, matching, profili, metriche, export…). **Manca solo il modo di leggerla dal sistema**: questo backend lo fornisce.

## 1. Contesto e scopo

Ogni azione rilevante del sistema è stata auditata fin dall'inizio (login, `profile_viewed`, `profiles_searched`, `matching_run`, `metrics_viewed`, `export_requested/approved/denied/downloaded`, `operator_created/disabled/…`, `interview_section_confirmed`). Ma finora nessun ruolo può **leggere** quel registro attraverso il sistema. L'Auditor è la figura che lo fa (§6): questo backend gli dà un endpoint di **consultazione in sola lettura** con filtri (chi/cosa/quando) e un endpoint di **verifica dell'integrità** della catena hash. Chiude il ciclo di accountability su cui poggia l'intera postura §2/§7.3.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora — backend):**
- **`GET /audit`** (permesso `READ_AUDIT`, solo ruolo `auditor`): elenco delle voci di audit **più recenti prima**, **paginato a cursore per id** (`before` + `limit`), con **filtri opzionali**: `actor`, `action`, `from`/`to` (intervallo su `occurred_at`).
- **`GET /audit/verify`** (`READ_AUDIT`): esegue la verifica della catena hash e restituisce l'esito (`{ok, broken_at, reason}`), rendendo **verificabile** la tamper-evidence (§7.3).
- **Voce di audit** restituita: `id`, `occurred_at`, `actor`, `action`, `target_pseudonym`, `details`. Gli hash interni (`prev_hash`/`record_hash`) **non** sono esposti (macchinari di integrità; l'esito è dato da `/audit/verify`).
- **Sola lettura**: nessuna mutazione; il server impone l'RBAC (403 per gli altri ruoli).

**Non-obiettivi (rimandati):**
- **Frontend** (visore del log, filtri UI, badge di integrità) → **spec successiva** (auditor-frontend).
- **Attività operatori del Supervisore** (§6): vista aggregata/filtrata sugli stessi dati → sotto-progetto successivo, costruito sopra questo contratto.
- **Esportazione del log** / reportistica → fuori scope (il log è consultazione dell'auditor; un eventuale export passerebbe comunque dal flusso autorizzato §7.3, non ora).
- **Annotazioni/azioni dell'auditor**: nessuna — l'auditor «non modifica nulla» (§6).
- **Ancoraggio esterno / HMAC della catena** → Fase 2 (come da §14): qui si **verifica** la catena esistente, non la si irrobustisce.

## 3. Decisioni di design (con motivazione)

1. **Sola lettura, e la lettura NON viene auditata (opzione approvata).** `GET /audit` e `/audit/verify` sono letture pure: **non** appendono un evento «audit_viewed». *Perché §6:* l'auditor «non modifica nulla»; aggiungere una scrittura al suo percorso di lettura contraddirebbe il ruolo (e la natura read-only del ruolo DB `bussola_auditor`). A differenza delle letture di **dati di profilo** da parte di operatori (che sono auditate perché sensibili), la lettura del registro **da parte dell'auditor** è essa stessa il meccanismo di garanzia, non un'operatività da tracciare.

2. **Paginazione a cursore per `id` decrescente (opzione approvata).** `GET /audit?before=<id>&limit=<n>` → le `n` voci con `id < before` (o le ultime, se `before` assente), ordinate per `id DESC`. *Perché §7.3:* il log è **append-only** e cresce nel tempo; il cursore per id (monotono con l'ordine di append) è **stabile** — nessuno slittamento di pagina mentre arrivano nuove righe — e modella naturalmente lo «scorrere indietro nel tempo». `limit` ha un **default** e un **tetto massimo** (prevenzione abusi §3, niente dump illimitati in una richiesta).

3. **Filtri chi/cosa/quando (opzione approvata).** `actor` (match esatto sull'username), `action` (match esatto sul nome-azione), `from`/`to` (intervallo su `occurred_at`). Tutti opzionali, combinabili col cursore. *Perché §6:* l'auditor verifica «chi ha fatto cosa e quando»; questi tre assi coprono la domanda senza costruire un motore di query generico (YAGNI).

4. **Verifica della catena esposta (opzione approvata).** `GET /audit/verify` esegue `verify_audit_chain` (già esistente, S2) → `{ok, broken_at, reason}`. *Perché §7.3:* la catena hash rende il log **tamper-evident**; senza un modo di verificarla dal sistema, la garanzia resta teorica. L'auditor ottiene una risposta netta: catena integra, oppure prima riga che la rompe.

5. **La voce espone chi/cosa/quando/details, non gli hash.** `prev_hash`/`record_hash` sono macchinari interni; esporli nell'elenco sarebbe rumore. *Perché:* l'auditor legge **azioni**; l'integrità è una domanda separata risolta da `/audit/verify`.

6. **RBAC applicativo, server autorità; connessione via ruolo app.** `require_permission(READ_AUDIT)` (solo `auditor`); la connessione usa `get_conn` (ruolo DB `bussola_app`, che ha `SELECT` sull'audit per la catena). *Perché §6:* le distinzioni tra ruoli sono **RBAC applicativo** (come da STATO_TECNICO §6); il ruolo DB `bussola_auditor` resta difesa-in-profondità. Nessuno stato ambiguo (fail-closed).

7. **Nessun rischio §2 di sorveglianza.** Il log traccia le **azioni degli operatori** (accountability sullo staff) e riferimenti a **pseudonimi opachi** (`target_pseudonym`), mai dati personali della persona detenuta né inferenze/punteggi. *Perché §2:* la vista serve a impedire il riuso improprio, non a profilare le persone.

## 4. Unità e confini

Sotto `backend/src/bussola/`:
- **`data/audit.py`** (estensione) — `AuditEntry` (modello di sola lettura: `id, occurred_at, actor, action, target_pseudonym, details`) + `list_audit(conn, *, before=None, limit=…, actor=None, action=None, from_ts=None, to_ts=None) -> list[AuditEntry]`. `verify_audit_chain` **già esiste** (riuso).
- **`api/routers/audit.py`** (nuovo) — `GET /audit` (query params → `list_audit`) e `GET /audit/verify` (→ `verify_audit_chain`), entrambi dietro `require_permission(READ_AUDIT)`; `limit` con default e cap.
- **`api/app.py`** — include il router.

Confine: legge dalla tabella esistente `audit.audit_log`; nessuna nuova tabella/migrazione; nessuna dipendenza dal frontend. Il server resta l'autorità (RBAC/403).

## 5. Flusso e contratto HTTP

```
[auditor READ_AUDIT]
  GET /audit?before=<id>&limit=<n>&actor=<u>&action=<a>&from=<iso>&to=<iso>
     → 200 [AuditEntry…]  (id DESC, id<before se dato, filtri applicati; limit cap-ato)
  GET /audit/verify
     → 200 { ok: bool, broken_at: int|null, reason: str|null }
[ruolo diverso da auditor] → 403 (require_permission)
[token assente/scaduto] → 401
```

`AuditEntry` = `{ id: int, occurred_at: datetime, actor: str|null, action: str, target_pseudonym: str|null, details: object }`.

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**; `pytest` con DB di test (fixtures `db`/`app_conn`/`client`/`make_operator`). Si semina il log con `append_audit(...)`. Priorità (tenuta del sistema, §9):
- **RBAC (server autorità):** un `auditor` ottiene 200 su `/audit` e `/audit/verify`; **ogni altro ruolo** (operator/supervisor/admin) ottiene **403** — la lettura del log è vincolata al ruolo.
- **Nessuna scrittura sulla lettura:** dopo `GET /audit`/`/audit/verify`, il numero di righe del log è **invariato** (nessun evento «audit_viewed» appeso) — coerente con §6 «non modifica nulla».
- **Cursore + ordine:** `list_audit` restituisce le voci per `id DESC`; con `before=<id>` restituisce solo `id < before`; `limit` limita il numero e il **cap** massimo è imposto.
- **Filtri:** `actor`/`action` filtrano per match esatto; `from`/`to` restringono per `occurred_at`; combinati col cursore.
- **Verifica catena:** su un log integro `/audit/verify` → `{ok: true}`; su una catena manomessa (riga alterata nel DB di test) → `{ok: false, broken_at: <id>}`.
- **Voce:** `AuditEntry` espone `id/occurred_at/actor/action/target_pseudonym/details` e **non** `prev_hash`/`record_hash`.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Lettura del log da un ruolo non autorizzato | `require_permission(READ_AUDIT)` (solo auditor) → 403; server autorità |
| La lettura dell'auditor «sporca» il log | letture pure, nessun evento appeso (§6 «non modifica nulla») |
| Dump illimitato in una richiesta | `limit` con cap massimo (§3 prevenzione abusi) |
| Slittamento di pagina su log che cresce | cursore per `id` (append-only, monotono), non offset |
| Tamper-evidence solo teorica | `/audit/verify` rende verificabile la catena (§7.3) |
| Frainteso come sorveglianza sulle persone | il log traccia **azioni degli operatori** + pseudonimi opachi, mai dati/inferenze sulla persona (§2) |

## 8. Criteri di accettazione

- `list_audit` corretto su cursore/limit/cap/filtri/ordine; `/audit` e `/audit/verify` restituiscono i contratti §5; **403 per i non-auditor**, 200 per l'auditor; **nessuna riga aggiunta** dalle letture; `/audit/verify` distingue catena integra vs manomessa. `pytest -q`, `ruff check .`, `mypy src` verdi.
- Nessuna nuova tabella/migrazione. Solo dipendenze open source permissive (nessuna nuova). `operator-portal/` e `frontend/` **non toccati** (parte backend).

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§6/§7.3/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con l'endpoint di lettura audit + verifica, la scelta «lettura non auditata» (auditor read-only), la paginazione a cursore, e l'avanzamento della roadmap (auditor-frontend; poi attività-operatori supervisore, admin-config).
- **Spec auditor-frontend (successiva):** il visore del log (elenco paginato + filtri + badge integrità) sul contratto di questa spec.
- **Piano collegato:** scomposizione TDD (`AuditEntry` + `list_audit` con cursore/filtri e i suoi test; poi il router `/audit` + `/audit/verify` con RBAC e i test d'integrazione).
