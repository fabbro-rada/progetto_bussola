# Spec di design — Sottosistema 29: Colloqui di follow-up (Fase 2·A)

**Progetto «Bussola»** · Sottosistema 29 (Fase 2, §8 — «colloqui di follow-up per aggiornare il profilo in base all'esperienza lavorativa in corso») · *Design di riferimento per il piano collegato* · 2026-07-29

---

## 0. Cos'è questo documento

Spec di design del **secondo sotto-progetto della Fase 2**: i **colloqui di follow-up**, cioè colloqui successivi al primo che **aggiornano un profilo lavorativo esistente** in base all'esperienza di lavoro/formazione svolta nel frattempo (§7.2/§8). Tocca il **ciclo centrale** (motore colloquio S4, kiosk S8/S9/S10, profilo/persistenza) ed è vincolato dalle linee rosse: §2 (solo-lavoro, no sorveglianza/punteggi), §4 (volontarietà, non-coercizione, brevità, consenso), §5 (pseudonimizzazione, minimizzazione, conferma dalla persona, **nessuna mappa persona↔pseudonimo nel sistema**), §6/§7.3 (ruoli, azione operatore auditata), §9 (TDD, solo dati sintetici), §11 (codice inglese, i18n). **Nessuna modifica al nucleo protetto.**

## 1. Contesto e scopo

Un profilo vale se resta aderente alla realtà nel tempo (§5). Dopo il primo colloquio la persona spesso svolge un'esperienza lavorativa/formativa in carcere: il follow-up cattura quell'esperienza e aggiorna il profilo (nuova esperienza, competenze ora *dimostrate*, aspirazioni evolute), migliorando il matching. Il vincolo non-negoziabile: farlo **senza** che il sistema memorizzi chi è la persona. Il codice già lo prevede — `data/pseudonym.py`: «the system never stores the link between a pseudonym and a real person — that register lives outside the system». Il follow-up sfrutta questo: il ri-collegamento passa da un **token monouso** emesso dall'operatore (che identifica la persona col registro esterno), mai da un'anagrafica nel sistema.

## 2. Obiettivi e non-obiettivi

**Obiettivi:**
- **Token di follow-up (ri-collegamento §5).** L'operatore emette dal portale un token **monouso, a scadenza, legato a UNO pseudonimo**; memorizzato solo come **hash**; il sistema mappa **token→pseudonimo**, mai token→persona. La persona lo usa al kiosk per aggiornare *quel* profilo.
- **Colloquio focalizzato** (riusa il motore S4): chiede l'esperienza lavorativa/formativa recente → **aggiunge** una `WorkExperience`, **alza il grado di evidenza** delle competenze che l'esperienza dimostra, **rivede** le aspirazioni se cambiate. Non ri-percorre tutte le sezioni.
- **Aggiornamento in-place** dello stesso profilo (append esperienza, upgrade evidenza; dati precedenti confermati **preservati**), con **audit** dell'evento di follow-up. **Nessuna storicizzazione delle versioni** (minimizzazione §5).
- **Volontarietà (§4):** il follow-up si apre con consenso/recap; la persona può **rifiutare** e fermarsi in ogni momento; token perso/scaduto → nessun follow-up (ri-provisionabile).
- **Auditabilità (§6/§7.3):** emissione token e completamento follow-up sono eventi auditati.

**Non-obiettivi (esclusi):**
- **Mappa persona↔pseudonimo nel sistema.** Mai. Il registro resta esterno.
- **Storicizzazione delle versioni del profilo** (snapshot). Rimandata (§14) — la minimizzazione §5 prevale; se servisse la progressione per la reportistica, decisione separata.
- **Refresh completo del profilo** (ri-percorrere tutte le sezioni): scartato (oneroso, contro la brevità §4).
- **Auto-provisioning / re-identificazione automatica** (biometria, anagrafica): vietato (§2/§5).
- **Colloqui di follow-up iniziati dalla persona senza operatore** (self-service via codice tenuto dalla persona): scartato in favore del provisioning operatore (fedele all'architettura «registro esterno»).

## 3. Decisioni di design (con motivazione)

1. **Ri-collegamento via token operatore, non via anagrafica (§5).** Il legame persona↔pseudonimo vive **fuori dal sistema** (già così, `data/pseudonym.py`). L'operatore — ruolo §6 che «fa funzionare il reinserimento» e consulta i profili — identifica la persona col registro esterno e **provisiona** un follow-up per uno pseudonimo. Il sistema memorizza solo `hash(token)→pseudonimo` (+ scadenza, monouso). *Perché:* rispetta §5 alla lettera (nessuna identità nel sistema) riusando il modello già scelto; l'operatore è l'autorità §6 appropriata.

2. **Token monouso, a scadenza, hashed (come i token di sessione S5/S8).** Alta entropia (`secrets.token_urlsafe`), TTL breve, consumato al primo uso riuscito, in DB solo l'hash. *Perché:* §7.3 prevenzione abusi; un token che vive troppo o riusabile è una superficie di rischio; l'hash evita che una lettura del DB riveli token attivi. **Non** è una credenziale della *persona* (che non gestisce segreti), ma un artefatto operativo effimero.

3. **Colloquio focalizzato che riusa il motore S4, non un nuovo motore.** Il follow-up è una **variante di ambito** dell'`Interview` esistente: stesse garanzie (estrazione per-sezione validata, riepilogo & conferma dalla persona, chiarimento gentile delle incongruenze) ma **caricando il profilo esistente** e percorrendo un set di sezioni ridotto (esperienza recente → competenze evidenziate → aspirazioni). *Perché §5/§0:* non si reinventa il motore né si toccano le garanzie del nucleo; si estende il ciclo centrale in modo additivo.

4. **Aggiornamento in-place, append dei dati, nessuno storico (minimizzazione §5).** Il profilo resta l'unica «verità corrente» confermata dalla persona: la nuova esperienza è **aggiunta** (le precedenti non si perdono), l'evidenza di una competenza può **salire** (es. `declared`→`demonstrated`), le incongruenze si risolvono col meccanismo di chiarimento S4. `updated_at` avanza; l'audit registra `followup_completed`. *Perché:* §5 minimizzazione (non si accumulano snapshot per-persona); §5 realismo (confermato dalla persona).

5. **Volontarietà e non-coercizione esplicite (§4).** Il follow-up al kiosk **si apre con un recap/consenso** dedicato («vuoi aggiornare il tuo profilo con l'esperienza recente?») e la persona può **rifiutare** senza conseguenze; il pulsante «Ferma» resta sempre attivo. *Perché:* un follow-up provisionato da un operatore non deve diventare una convocazione obbligata; la partecipazione resta libera.

6. **Nuovo permesso minimo `PROVISION_FOLLOWUP` per l'operatore.** L'emissione del token è gated su un permesso dedicato (non un allargamento di permessi esistenti), assegnato al ruolo **operatore**. *Perché §6:* privilegio minimo; l'azione è distinta dalla consultazione/ matching.

## 4. Unità e confini

**Backend** (`backend/src/bussola/`):
- **`data/migrations/0008_followup.sql`** (nuovo) — tabella `interview.followup_token` (o schema esistente adeguato): `token_hash text PK`, `pseudonym_id text`, `created_at timestamptz`, `expires_at timestamptz`, `used_at timestamptz NULL`. Grant `bussola_app` SELECT/INSERT/UPDATE; auditor nessun accesso.
- **`followup/…`** (nuovo) — `FollowupTokenService`: `issue(pseudonym_id, *, actor) -> token` (genera token, salva hash+TTL, audit `followup_provisioned`); `consume(token) -> pseudonym_id | None` (verifica hash/scadenza/uso, marca usato, fail-closed).
- **`interview/…`** (modifica additiva) — l'`Interview` accetta una modalità **follow-up**: costruita su un **pseudonimo esistente** (carica il `WorkProfile` corrente invece di `create_new()`), percorre le sezioni ridotte, e al termine **fa append/upgrade** invece di creare. Le garanzie (estrazione validata, riepilogo/conferma, chiarimento) restano.
- **`auth/rbac.py`** (modifica) — nuovo `Permission.PROVISION_FOLLOWUP`, assegnato a `Role.OPERATOR`.
- **`api/routers/…`** — endpoint operatore `POST /followups` (emette token per uno pseudonimo, `PROVISION_FOLLOWUP`, audit); endpoint kiosk `POST /kiosk/interview/start-followup` (consuma il token → sessione follow-up sul profilo). Audit `followup_completed` a fine colloquio.

**Frontend:**
- **Kiosk** (`frontend/`): schermata d'inserimento token di follow-up (o parametro di start), schermata **consenso/recap di follow-up**, poi il flusso colloquio esistente sulle sezioni ridotte; riusa le schermate/patterns S9/S10. «Ferma» sempre attivo.
- **Portale operatore** (`operator-portal/`): nel dettaglio profilo (S13), azione **«Nuovo follow-up»** → mostra il **token monouso** da consegnare alla persona (una tantum, non ripersistito in chiaro; pattern della temp-password S14).

**Confine:** nessuna modifica al reporting (S28), al matching, o alle linee rosse. Nessuna anagrafica introdotta. Il motore S4 è esteso in modo additivo (la modalità primo-colloquio resta invariata).

## 5. Interfacce delle nuove astrazioni

- **`FollowupTokenService.issue(pseudonym_id: str, *, actor: str) -> str`** — ritorna il token in chiaro (mostrato una volta); persiste `hash(token)`, `pseudonym_id`, `expires_at`; audit `followup_provisioned` (target = pseudonimo). **`.consume(token: str) -> str | None`** — ritorna lo pseudonimo se il token è valido/non scaduto/non usato (e lo marca usato, in transazione), altrimenti `None` (fail-closed).
- **`Interview` (modalità follow-up)** — costruzione su pseudonimo esistente; espone lo stesso contratto turn-by-turn di S8 (`start`/`submit` → `Step`), ma la prima azione carica il profilo e imposta le sezioni ridotte; al termine `followup_completed` audit + profilo aggiornato (append/upgrade).
- **`Permission.PROVISION_FOLLOWUP`** — operatore.
- **HTTP:** `POST /followups {pseudonym_id}` → `{token}` (operatore); `POST /kiosk/interview/start-followup {token}` → `{session_token, step}` o rifiuto fail-closed (token invalido → `unauthorized`/`unavailable`, degrado kiosk).

## 6. Strategia di test (§9)

- **Token (prioritario, §5/§7.3):** monouso (secondo uso → rifiutato), scadenza (dopo TTL → rifiutato), in DB solo l'hash (mai il token in chiaro né lo pseudonimo-in-chiaro accostato a un'identità); `consume` fail-closed su token ignoto/scaduto/usato; **nessuna colonna anagrafica** nella tabella.
- **Ri-collegamento corretto:** un follow-up con token per `P-x` carica ed aggiorna **solo** `P-x`; non è possibile aggiornare uno pseudonimo arbitrario senza un token valido emesso per esso.
- **Aggiornamento append/upgrade:** la nuova esperienza è aggiunta (le precedenti restano), l'evidenza sale dove dimostrata, i dati confermati non vengono persi; `followup_completed` auditato; **nessuno snapshot storico** creato.
- **Volontarietà (§4):** percorso di **rifiuto** del follow-up (la persona declina → nessuna modifica al profilo); «Ferma» interrompe senza danni.
- **Garanzie S4 preservate:** estrazione validata, riepilogo/conferma, chiarimento incongruenze funzionano in modalità follow-up (riuso, non riscrittura).
- **RBAC/audit:** `POST /followups` → 403 per non-operatore; emissione e completamento auditati; il kiosk resta dietro token di dispositivo.
- **Invarianza primo-colloquio:** la modalità primo-colloquio (S4/S8) resta identica — suite S4/S8 verdi **senza modifiche alle asserzioni**.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Introdurre di fatto una mappa persona↔pseudonimo | il sistema salva solo `hash(token)→pseudonimo`; l'identità resta nel registro esterno (operatore) |
| Token come superficie di abuso | monouso, TTL breve, alta entropia, in DB solo hash, fail-closed su consume |
| Coercizione (follow-up «obbligato») | consenso/recap all'avvio, rifiuto senza conseguenze, «Ferma» sempre attivo (§4) |
| Perdita di dati nel profilo | append (non overwrite); i dati confermati restano; chiarimento gentile per le incongruenze |
| Regressione del primo colloquio | modalità follow-up **additiva**; suite S4/S8 invariate (criterio d'accettazione) |
| Accumulo di dati per-persona | nessuno storico versioni (minimizzazione §5); solo la verità corrente + audit |

## 8. Criteri di accettazione

- Suite backend (pytest/ruff/mypy) e frontend (vitest/typecheck/lint/build) **verdi**; suite S4/S8/S9 del primo colloquio verdi **senza modifiche alle asserzioni**.
- Token monouso/scaduto/hashed verificati; `consume` fail-closed; **nessuna colonna anagrafica**; il follow-up aggiorna **solo** lo pseudonimo del token.
- Aggiornamento **append/upgrade in-place**, dati precedenti preservati, **nessuno storico**; `followup_provisioned`/`followup_completed` auditati.
- Volontarietà: percorso di rifiuto e «Ferma» funzionanti.
- `PROVISION_FOLLOWUP` solo operatore (403 altrimenti). Nessuna modifica al nucleo, al reporting, al matching, alle linee rosse.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme §2/§4/§5/§6/§7.3/§9/§11. **Nessuna modifica al nucleo.** Il follow-up è esplicitamente Fase 2 (§8). Il ri-collegamento rispetta §5 riusando il modello «registro esterno» già codificato.
- **`STATO_TECNICO.md`**: alla conclusione, riga §15 (Sott. 29) + follow-up §14 (chiude «colloqui di follow-up = Fase 2»); nota lo storico-versioni come possibile evoluzione futura se emergesse un bisogno di progressione.
- **Piano collegato:** scomposizione TDD — (1) migrazione 0008 + `followup_token`; (2) `FollowupTokenService` (issue/consume, hash/TTL/monouso); (3) `PROVISION_FOLLOWUP` + `POST /followups` (operatore, audit); (4) modalità follow-up dell'`Interview` (load profilo + sezioni ridotte + append/upgrade); (5) `POST /kiosk/interview/start-followup` (consume → sessione); (6) kiosk: inserimento token + consenso/recap follow-up + flusso; (7) portale: azione «Nuovo follow-up» nel dettaglio profilo (token una-tantum).
