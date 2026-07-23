# Spec di design — Sottosistema 6: Portale operatore — core matching

**Progetto «Bussola»** · Sottosistema 6 · *Design di riferimento per il piano collegato* · 2026-07-23

---

## 0. Cos'è questo documento

Spec di design del sesto sottosistema, nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (linee rosse, «mai una scatola nera»), §3 (locale, open source permissivo, budget nullo, prevenzione abusi), §4 (spiegabilità, non giudizio), §5 (profilo solo-lavoro), §6 (ruoli/privilegio minimo/audit), §7.2 (funzioni del portale operatore), §7.3 (audit immutabile), §9 (TDD, dati sintetici), §10 (matching spiegabile con gap formativi). Poggia su S1 (`WorkProfile`/enum), S2 (`ProfileRepository`, audit, ruoli DB), S3 (client LLM, constrained decoding), S5 (auth, RBAC, layer FastAPI, `require_permission`).

## 1. Contesto e scopo

Realizza il **cuore lato-operatore del ciclo centrale di Fase 1**: l'operatore inserisce le **richieste di lavoro** delle aziende, avvia il **matching spiegabile** con i profili delle persone e ne consulta i risultati con il *perché* e i **gap formativi**. È il pezzo che completa la promessa del §10 («il matching è spiegabile e propone i gap formativi»). È backend/API: il frontend (S7) lo consumerà.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Richieste di lavoro** (CRUD): l'operatore inserisce posizioni con competenze richieste, vincoli, prerequisiti formativi (§7.2).
- **Matching spiegabile** per-richiesta → profili candidati ordinati, ciascuno con il *perché* (requisito per requisito) e i **gap formativi** con formazione consigliata (§10, §4).
- **Consultazione/ricerca profili** (filtri per competenze, lingue, disponibilità) (§7.2).
- **Integrazione** RBAC (S5, attiva i permessi §6 dichiarati) + audit (S2) su ogni operazione rilevante.

**Non-obiettivi (rimandati):**
- **Metriche minime** e **esportazione di base con autorizzazione** (§7.2/§7.3) → follow-on dedicato.
- **Persistenza degli esiti di matching** → Fase 2 (in Fase 1 il matching è calcolato on-demand).
- **Orientamento autonomo alla ricerca del lavoro** (portali pubblici) → escluso dal perimetro (§7.3).
- **Frontend/kiosk** → S7.

## 3. Decisioni di design (con motivazione)

1. **Matching ibrido: vincoli deterministici + giudizio semantico LLM ancorato.** I dati del profilo (competenze, settori, aspirazioni) sono **testo libero in 5 lingue**: un confronto per stringhe fallisce (sinonimi, granularità, lingue diverse). Le due sole vie sono una **tassonomia controllata** (da mantenere) o un **LLM**. Si sceglie un **ibrido**: le dimensioni a enum sono deterministiche, l'idoneità semantica sul testo libero è giudicata dall'LLM con output **strutturato e ancorato**. *Perché §2/§10:* spiegabile per costruzione (vedi §3.3), niente tassonomia da mantenere, multilingua nativo, LLM locale già disponibile a costo marginale zero.

2. **Gate deterministico dei vincoli rigidi PRIMA dell'LLM.** Disponibilità, conflitti di vincolo (es. posizione con turni notturni vs `no_night_shifts`), livello di lingua minimo sono **regole**: o compatibili o no. I non-compatibili sono **esclusi con motivo esplicito**, mai «ragionati via» dall'LLM. *Perché §2/§9:* i non-negoziabili restano prevedibili e testabili; e si limitano le chiamate LLM (il giudizio semantico gira solo sui sopravvissuti).

3. **Spiegabilità = output strutturato e ancorato, non punteggi opachi.** Per ogni abbinamento: rank + punteggio, **elenco dei requisiti** (soddisfatto/no + **evidenza citata dal profilo**), **vincoli** (compatibile/conflitto con motivo), **gap** con formazione consigliata. Il punteggio è la **somma dei contributi mostrati**, non un numero calato dall'alto. *Perché §2 («mai una scatola nera») e §4 («il perché in forma comprensibile»):* l'operatore vede il motivo voce per voce; questo è più trasparente di un punteggio grezzo.

4. **L'LLM giudica SOLO l'idoneità lavorativa, mai la persona.** Il prompt vincola il modello a confrontare le competenze/esperienze con i requisiti espliciti della posizione; nessun giudizio, punteggio di pericolosità, o inferenza extra-lavorativa. Il profilo è **solo-lavoro per costruzione** (§5): non c'è materiale sensibile su cui derivare. *Perché §2/§4.*

5. **Matching calcolato on-demand, non persistito (Fase 1).** Ogni run è **auditato** (`matching_run`, `actor`=operatore, `details` whitelist: id richiesta, n. candidati) ma gli esiti non sono salvati. *Perché:* semplicità e minimizzazione; la persistenza/storicizzazione è una naturale estensione Fase 2.

6. **Gap → formazione consigliata dai requisiti non soddisfatti.** La formazione consigliata deriva dai requisiti/prerequisiti non soddisfatti, incrociata con `desired_training` della persona quando presente. *Perché §10:* orientamento formativo integrato, senza un catalogo esterno da mantenere in Fase 1.

7. **Testabilità come per il colloquio (S4).** Constrained JSON + `temp 0`; unit con **LLM finto** deterministici; un **test d'integrazione col modello reale** con personas sintetiche e asserzioni robuste (un match forte con un gap; un profilo escluso da un vincolo rigido). *Perché §9:* il pattern che in S4 ha fatto emergere difetti veri.

## 4. Unità e confini

Nuovo package **`bussola.matching`**:
- `models.py` — `JobRequest` (+ DTO di richiesta/risposta), tutti Pydantic `extra="forbid"`.
- `hard_constraints.py` — gate deterministico: `evaluate(profile, job) -> ConstraintResult` (compatibile? conflitti con motivo).
- `semantic.py` — `judge_requirements(client, profile, job, language) -> list[RequirementVerdict]` (constrained JSON ancorato; fail-safe: requisito non soddisfatto senza evidenza).
- `scoring.py` — compone gate + verdetti → `MatchResult` (rank, punteggio, contributi).
- `gaps.py` — requisiti non soddisfatti → formazione consigliata (incrocio con `desired_training`).
- `service.py` — `MatchingService`: `match(job_request_id) -> list[MatchResult]` (orchestrazione: carica candidati, gate, semantico sui sopravvissuti, scoring, gap; audita).
- `requests.py` — `JobRequestRepository` (CRUD su `matching.job_request`, senza commit interno).

Estensioni:
- **`bussola.data.profiles`**: `ProfileRepository.search(...)` + `list(...)` (filtri).
- **`bussola.data`**: migrazione `0005_job_requests.sql` (schema `matching`).
- **`bussola.api`**: router `job_requests.py`, `matching.py`, `profiles.py` (operator-gated, riusa `require_permission` S5).

Confine: `bussola.matching` dipende da `bussola.{profile,data,llm}`. `bussola.api` espone gli endpoint. Nessuna logica di metriche/export. Non conosce voce né UI.

## 5. Modello dati

Nuovo schema `matching` (AUTHORIZATION `bussola_owner`); `bussola_app` SELECT/INSERT/UPDATE (no DELETE); `bussola_auditor` nessun accesso.

- `matching.job_request`: `id`, `title`, `sector`, `description`, `required_skills` (testo[]), `required_languages` (jsonb: `[{language, min_level}]`), `required_availability` (text|null), `involves_night_shifts` (bool), `requires_full_time` (bool), `training_prerequisites` (testo[]), `created_by`, `created_at`, `updated_at`. **Nessun** campo discriminatorio/extra-lavorativo.

I profili restano in `profiles.work_profile` (S2, JSONB). Il matching non crea tabelle di esiti (on-demand, §3.5).

## 6. Flusso di matching (una `JobRequest`)

```
carica i profili candidati (tutti, o filtrati)
per ogni profilo:
   hard_constraints.evaluate(profile, job)
        non compatibile  → ESCLUSO con motivo (disponibilità / conflitto vincolo / lingua sotto livello)
        compatibile      → passa al semantico
semantic.judge_requirements(profilo sopravvissuto, job): per ogni required_skill/prerequisito
        → {requisito, soddisfatto, evidenza(citazione dal profilo|null)}   [constrained JSON, temp 0]
scoring: punteggio = Σ contributi requisiti soddisfatti (pesati per grado di evidenza) ; rank
gaps: requisiti non soddisfatti → formazione consigliata (∪ desired_training)
→ MatchResult{pseudonym, rank, score, requirements[], constraints[], gaps[]}
audit: matching_run (actor, job_request_id, n. candidati)
```

## 7. Superficie HTTP + RBAC + audit

- `POST /job-requests`, `GET /job-requests`, `GET /job-requests/{id}` — `require_permission(MANAGE_JOB_REQUESTS)`.
- `POST /job-requests/{id}/match` → lista `MatchResult` spiegati — `require_permission(RUN_MATCHING)`; audita `matching_run`.
- `GET /profiles` (ricerca/filtri), `GET /profiles/{pseudonym}` — `require_permission(READ_PROFILES)`; audita `profile_viewed`.
- Attiva i permessi §6 già dichiarati in S5 (`MANAGE_JOB_REQUESTS`/`RUN_MATCHING`/`READ_PROFILES` = ruolo operatore). `actor` sempre dalla sessione autenticata; `details` audit whitelist.

## 8. Strategia di test (§9)

TDD; **solo dati sintetici** (personas + richieste varie). Priorità:
- **Gate deterministico**: compatibilità disponibilità, conflitti di vincolo (notturni/full-time), lingua sotto livello → esclusione **con motivo**; `flexible` compatibile.
- **Semantico (LLM finto)**: parsing/validazione dei verdetti ancorati; fail-safe (requisito non soddisfatto se output non valido).
- **Scoring/rank** deterministico dai verdetti; **gap → formazione** (incl. incrocio `desired_training`).
- **RBAC**: ogni endpoint gated dal permesso giusto; ruolo non abilitato → 403.
- **Audit**: `matching_run`/`profile_viewed` registrati (actor + details whitelist).
- **Ricerca profili**: filtri per disponibilità/lingua/note/competenze.
- **Integrazione col modello reale** (`requires_llm`): un match forte con un gap rilevato + un profilo escluso da un vincolo rigido; spiegazione **ancorata** (l'evidenza cita davvero il profilo), nessun giudizio extra-lavorativo.

## 9. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Scatola nera / punteggio opaco (§2) | Output strutturato ancorato per requisito; punteggio = somma dei contributi mostrati |
| LLM «ragiona via» un vincolo rigido | I vincoli rigidi sono un gate deterministico PRIMA dell'LLM; l'LLM non li tocca |
| LLM inventa un match non ancorato | Prompt richiede evidenza citata dal profilo; fail-safe = non soddisfatto; test d'integrazione verifica l'ancoraggio |
| Giudizio sulla persona (§2/§4) | Prompt limitato all'idoneità lavorativa; profilo solo-lavoro per costruzione |
| Costo/latency LLM su molti profili | Gate deterministico riduce i candidati prima del semantico |
| Non determinismo nei test | LLM finto per gli unit; reale solo per l'integrazione (temp 0, asserzioni robuste) |
| Criteri discriminatori nella richiesta | `JobRequest` è una whitelist solo-lavoro (`extra="forbid"`), nessun campo sensibile |

## 10. Criteri di accettazione

- Unit (LLM finto) verdi e deterministici: gate, semantico, scoring/rank, gap, RBAC, audit, ricerca.
- Con Qwen2.5 reale: matching sintetico end-to-end con spiegazione **ancorata** e un gap formativo; un candidato escluso da un vincolo rigido con motivo; nessun giudizio extra-lavorativo; nessuna fuga.
- `pytest`, `ruff`, `ruff format --check`, `mypy` verdi. Nessuna nuova dipendenza non permissiva.

## 11. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§4/§5/§6/§7.2/§7.3/§9/§10). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con il matching ibrido (gate deterministico + semantico LLM ancorato), lo schema `matching`, la ricerca profili, gli endpoint operatore e i permessi §6 attivati.
- **Piano collegato:** scomposizione eseguibile in TDD (gate deterministico e RBAC/audit prima; poi semantico, scoring/gap, endpoint, integrazione reale).
