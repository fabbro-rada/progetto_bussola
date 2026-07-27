# Spec di design — Sottosistema 13: Portale operatore — Consultazione profili

**Progetto «Bussola»** · Sottosistema 13 (portale operatore, sotto-progetto 3/5) · *Design di riferimento per il piano collegato* · 2026-07-26

---

## 0. Cos'è questo documento

Spec di design del **terzo sotto-progetto del portale operatore**: la **consultazione dei profili** lavorativi. Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (ambito solo-lavoro), §3 (locale, open source, solo azioni previste), §5 (profilo minimo, pseudonimo, **grado di evidenza**), §6 (ruolo operatore, privilegio minimo), §7.2 (consultazione dei profili, ricerca e filtri), §7.3 (audit dell'enumerazione, resistenza abusi, no export non autorizzato), §9 (TDD, dati sintetici), §11 (codice inglese, stringhe UI esternalizzate). Si innesta sullo scheletro S11 (`operator-portal/`) e riusa i pattern S12 (`operatorClient` esteso, `useApiError`, nav-link `built`). Consuma l'API S6: `GET /profiles?availability=&language=&note=&skill_query=` → `WorkProfile[]` e `GET /profiles/{pseudonym}` → `WorkProfile | 404`.

## 1. Contesto e scopo

Con S12 l'operatore lancia il matching da una richiesta. Questo sotto-progetto aggiunge la **consultazione diretta dei profili** (§7.2): cercare/filtrare le persone per competenze, lingue, disponibilità, categoria di nota operativa, e leggere il profilo lavorativo completo — anche fuori da una specifica richiesta. È il modo in cui l'operatore «trova le persone adatte alle posizioni» e conosce la popolazione lavorativa disponibile.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Sezione «Profili»**: ricerca/filtri (`GET /profiles`), lista risultati, dettaglio (`GET /profiles/{pseudonym}`), sotto la shell S11, dietro `ProtectedRoute` + ruolo operatore (`READ_PROFILES`). La voce di nav (placeholder S11) diventa un **link reale** (flag `built`).
- **Ricerca/filtri**: disponibilità (enum), lingua (testo), categoria nota operativa (enum), competenza (`skill_query`, testo). Filtri assenti omessi dalla query. **Ricerca senza filtri permessa** → lista completa (l'audit lato S6 la rende tracciabile, §7.3).
- **Dettaglio profilo solo-lavoro**: pseudonimo opaco, alfabetizzazione digitale, **competenze con kind + grado di evidenza (etichetta+colore: Certificata/Dimostrata/Dichiarata)**, lingue+livello, esperienze (ruolo/settore/durata), aspirazioni (interessi/disponibilità/vincoli), formazione desiderata, note operative.
- **`operatorClient` esteso** fail-closed col Bearer; 401→`unauthorized` (→ logout via `useApiError`), 403→`forbidden`, 404 (get)→`not-found`, rete/5xx→`error`.
- **i18n** italiano esternalizzato, incluse le **mappe di etichette per gli enum** (grado evidenza, kind, livello lingua, alfabetizzazione, disponibilità, vincoli, categorie note).

**Non-obiettivi (rimandati):**
- **Export dei profili/risultati** → sotto-progetto 5 (export **con autorizzazione**, §7.3). Qui è **consult-only**.
- **Modifica dei profili**: i profili sono costruiti dalla persona nel colloquio (S4) e confermati da lei; l'operatore non li modifica (§5). Nessun endpoint di modifica.
- **Amministrazione utenze, metriche** → sotto-progetti 4–5.

## 3. Decisioni di design (con motivazione)

1. **Sezione coesa ricerca+lista+dettaglio, innestata sulla shell S11.** Rotte `/profiles`, `/profiles/:pseudonym`. *Perché §7.2:* «ricerca e filtri sui profili lavorativi» + «trovare le persone adatte»; stesso pattern coeso di S12.

2. **Ricerca senza filtri permessa (lista completa), coerente col backend.** *Perché §7.3:* l'enumerazione di massa è il vettore di abuso più ovvio, ma S6 la **audita** (nomi-filtro + conteggio, mai PII) invece di bloccarla; l'operatore ha bisogno di sfogliare. La UI resta fedele al contratto; la tracciabilità è la garanzia.

3. **Grado di evidenza a etichetta+colore (opzione approvata).** Ogni competenza mostra kind (Tecnica/Trasversale) e grado (**Certificata** verde / **Dimostrata** blu / **Dichiarata** grigio) come parola + colore di rinforzo. *Perché §5:* il valore del profilo dipende dall'aderenza alla realtà; il grado di evidenza è ciò che l'operatore deve poter valutare per un abbinamento; la parola è inequivocabile e il colore non è l'unico segnale (accessibilità).

4. **Consult-only, nessun export qui.** *Perché §7.3:* ogni condivisione verso l'esterno passa da un'autorizzazione (sotto-progetto 5); questa sezione legge soltanto.

5. **`operatorClient` esteso fail-closed + `useApiError`.** Come S12: risultati tipizzati, 401→onUnauthorized+/login, 403→«non autorizzato», error ritentabile. *Perché §3:* solo azioni previste, nessuno stato autenticato ambiguo.

6. **Pseudonimo opaco, nessuna PII, filtro a monte.** I `WorkProfile` sono solo-lavoro per costruzione (schema `extra="forbid"`) e le free-text sono già filtrate dalla PII a monte (S4/S6); la UI non reintroduce PII. *Perché §5/§7.3.*

## 4. Unità e confini

Sotto `operator-portal/src/`:
- **`api/operatorClient`** (estensione) — `searchProfiles(filters)`, `getProfile(pseudonym)`; risultati tipizzati; Bearer; fail-closed.
- **`types.ts`** (estensione) — `WorkProfile` + nested (`LanguageKnown`, `Skill`, `WorkExperience`, `Aspiration`, `DesiredTraining`) + enum (`DigitalLiteracy`, `EvidenceGrade`, `SkillKind`, `WorkConstraint`, `OperationalNoteCategory`), e `ProfileFilters`, result unions (`SearchProfilesResult`, `GetProfileResult`).
- **`screens/profiles/ProfileSearch`** — pannello filtri + risultati (righe compatte, link al dettaglio, empty-state).
- **`screens/profiles/ProfileDetail`** — vista solo-lavoro completa.
- **`screens/profiles/SkillBadge`** (o util) — l'etichetta di grado-evidenza (colore per grado).
- **`rbac/nav`** — «profiles» marcato `built`.
- **`shell/Nav`** — già rende link per gli item `built` (da S12).
- **`App`** — rotte annidate `/profiles`, `/profiles/:pseudonym`.
- **`i18n/locales/it`** (estensione) — stringhe della sezione + mappe di etichette enum.

Confine: dipende solo dal contratto HTTP S6 e dallo scheletro S11/pattern S12. Il server resta l'autorità (RBAC/403).

## 5. Flusso (una consultazione)

```
[operatore] Nav → «Profili» → /profiles
   (filtri opzionali) «Cerca» → GET /profiles?<filtri impostati>
      → WorkProfile[] → righe (pseudonimo · lingue · disponibilità · n° competenze) | empty-state
   riga → /profiles/:pseudonym
      GET /profiles/:pseudonym → dettaglio solo-lavoro (competenze con grado di evidenza, esperienze, aspirazioni, note…)
      404 → «profilo non trovato»
   401 in qualunque momento → onUnauthorized + /login («sessione scaduta») ; 403 → «non autorizzato» ; rete/5xx → errore ritentabile
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici** (profili finti). Vitest + @testing-library/react; `operatorClient` fake iniettato. Priorità:
- **Ricerca**: invia solo i filtri impostati come query params (omette i vuoti); i risultati rendono le righe con link al dettaglio; lista vuota → empty-state; ricerca senza filtri consentita.
- **Dettaglio**: rende tutte le sezioni solo-lavoro; ogni competenza mostra il **grado di evidenza corretto** (etichetta Certificata/Dimostrata/Dichiarata) e il kind; 404 → «profilo non trovato».
- **Etichette enum**: livelli lingua, disponibilità, vincoli, categorie note, alfabetizzazione digitale rese con le stringhe i18n corrette.
- **Degrado**: 401 → logout+redirect; 403 → «non autorizzato»; error → messaggio ritentabile.
- **Nav/RBAC**: «Profili» è un link reale; sezione dietro `ProtectedRoute`.
- **Privacy**: nessuna PII mostrata (solo pseudonimo + dati solo-lavoro) — verificato dalla struttura dei dati finti.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Enumerazione di massa dei profili | audit lato S6 (nomi-filtro+conteggio, mai PII); ricerca tracciabile, non nascosta |
| Fuga di PII nei testi liberi | filtro PII a monte (S4/S6); la UI non reintroduce; solo pseudonimo |
| Export non autorizzato | fuori scope qui; l'export (con autorizzazione) è il sotto-progetto 5 |
| Grado di evidenza frainteso | etichetta esplicita (parola) + colore di rinforzo, non solo colore |
| 401 su una chiamata lascia stato ambiguo | `useApiError` → onUnauthorized + redirect |

## 8. Criteri di accettazione

- Unit (fake client) verdi e deterministici: ricerca invia i filtri corretti/omette i vuoti; righe rese con link; empty-state; dettaglio rende tutte le sezioni + grado di evidenza per competenza; 404→non trovato; degrado 401/403/error; nav link reale.
- Il flusso `ricerca → risultati → dettaglio` è percorribile col fake client.
- `vitest`, typecheck, lint, build verdi. Solo dipendenze open source permissive (nessuna nuova prevista). `frontend/` (kiosk) intatto.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§5/§6/§7.2/§7.3/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con la sezione profili del portale, l'estensione `operatorClient`, la resa del grado di evidenza (etichetta+colore), la scelta «lista completa permessa e auditata», e l'avanzamento della roadmap (sotto-progetti 4–5).
- **Piano collegato:** scomposizione TDD (types + client `searchProfiles`/`getProfile`; poi ricerca+filtri+lista; poi il badge grado-evidenza + dettaglio; infine nav-link + composizione rotte + integrazione).
