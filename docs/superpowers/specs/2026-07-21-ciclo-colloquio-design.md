# Spec di design — Sottosistema 4: Ciclo centrale del colloquio

**Progetto «Bussola»** · Sottosistema 4 · *Design di riferimento per il piano collegato* · 2026-07-21

---

## 0. Cos'è questo documento

Spec di design del quarto sottosistema, nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §4 (dignità, non coercizione, non giudizio), §5 (validazione **con la persona**, incongruenze), §7.1 (colloquio a tappe, il sistema conduce, riepilogo & conferma), §7.3 (estrazione strutturata validata), §9 (TDD, dati sintetici). Poggia su S1 (`WorkProfile`), S2 (`ProfileRepository`, audit), S3 (`ScopeGuard`, client LLM, guardrail).

## 1. Contesto e scopo

Realizza il **motore conversazionale backend** del ciclo centrale: conduce il colloquio a tappe, estrae dati strutturati validati, riepiloga e fa **confermare dalla persona**, chiarisce le incongruenze con garbo, e persiste un profilo realistico — **senza consumare tempo degli operatori** (§5). È guidabile turno-per-turno; frontend/kiosk (S7) e voce (S5) lo consumeranno.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Colloquio guidato a tappe** deterministico (l'app conduce; l'LLM formula/estrae/verifica).
- **Estrazione per-sezione con constrained decoding** + validazione Pydantic verso lo schema whitelist.
- **Riepilogo & conferma dalla persona** a fine sezione e fine colloquio; correzione → ri-estrazione.
- **Rilevamento incongruenze** semantico (LLM) + domanda di chiarimento gentile.
- **Integrazione** guardrail (S3), profilo (S1), persistenza + audit (S2).
- **Degrado elegante** (LLM giù → messaggio controllato; il colloquio non si blocca).

**Non-obiettivi (rimandati):**
- **Frontend/kiosk** (accessibilità, RTL, comando «ferma» come UI) → S7.
- **Voce (STT/TTS)** → S5.
- **Ripresa a metà** di una sezione interrotta → Fase 2 (le sezioni confermate sono comunque persistite).
- **Colloqui di follow-up** → Fase 2 (§8).
- **Validazione serving su GPU** = fatta (primo passo di questo sottosistema, vedi §9-nota) — non è codice.

## 3. Decisioni di design (con motivazione)

1. **Flusso deterministico guidato dall'app; LLM per domande/estrazione/incongruenze.** Una macchina a stati conduce le tappe fisse; l'LLM formula le domande, interpreta le risposte, estrae, verifica incongruenze — ma **non decide il flusso**. *Perché §7.1* («il sistema conduce»): prevedibile, testabile, sicuro per una popolazione vulnerabile; niente derive agentiche.

2. **Estrazione per-sezione con constrained decoding.** Dopo il dialogo di una tappa, una chiamata LLM **vincolata allo JSON-schema** del sotto-modello di sezione (grammar/json_schema di llama.cpp) → il modello *non può* produrre campi fuori schema → validazione **Pydantic** (doppio controllo). *Perché §7.3:* estrazione strutturata validata, incrementale e allineata alla conferma per-sezione.

3. **Riepilogo & conferma dalla persona.** A fine sezione e fine colloquio, l'LLM riassume nella lingua ciò che ha capito; la persona **conferma o corregge**; su correzione si ri-estrae. *Perché §5:* è il meccanismo che rende il profilo realistico **senza impegnare gli operatori** — «chi conferma è la persona».

4. **Incongruenze: controllo LLM semantico + chiarimento gentile.** Sui dati confermati, un controllo LLM cerca incongruenze semantiche (durata che non torna, competenza in contrasto con le esperienze); se ne trova, il sistema **non accusa**: pone una domanda di chiarimento gentile e ri-conferma. *Perché §4/§5.*

5. **Guardrail su ogni risposta libera (S3).** La risposta della persona passa dal `ScopeGuard`; se fuori-tema/injection → rifiuto gentile e **ri-pongo la stessa domanda** (il colloquio non deraglia). Le domande/riepiloghi generati passano dall'output guard + filtro PII. *Perché §2/§7.3.*

6. **Stato in-memory + persistenza per-sezione.** `InterviewSession` in memoria (una postazione simultanea); ad ogni sezione confermata il profilo parziale è salvato via `ProfileRepository.save`. *Perché:* se la persona interrompe (§4/§7.1), le sezioni confermate restano; la ripresa a metà è Fase 2. Semplice e resiliente al giusto livello.

7. **Domande: template base i18n + adattamento LLM.** Ogni sezione ha domande base **esternalizzate** (5 lingue) come àncora prevedibile (e degrado elegante se l'LLM è lento/assente); l'LLM le rende naturali e genera i follow-up. *Perché §11 (i18n) + prevedibilità + §3 (degrado).*

## 4. Unità e confini

Nuovo package **`bussola.interview`**:

- `sections.py` — le tappe (competenze, esperienze, aspirazioni, vincoli, preferenze): sotto-schema Pydantic popolato, prompt d'estrazione, domande base i18n. Ordine fisso.
- `session.py` — `InterviewSession` (pseudonimo, lingua, indice sezione, `WorkProfile` parziale, stato).
- `extraction.py` — `extract_section(client, section, transcript, language) -> dict validato` (constrained decoding + Pydantic).
- `confirm.py` — `summarize(section, data, language)`, gestione conferma/correzione.
- `incongruence.py` — `find_incongruence(profile, language) -> Optional[ClarifyPrompt]`.
- `interview.py` — `Interview` orchestratore: `start(language)`, `submit(answer) -> Step` (dove `Step` è: domanda | riepilogo-da-confermare | chiarimento | fine), turno-per-turno, deterministico.
- Estende `bussola.llm.client` con l'output **vincolato** (json_schema/grammar) — usato dall'estrazione.

Confine: `bussola.interview` dipende da `bussola.{profile,guardrails,llm,data}`. Espone `Interview` (l'unico ingresso per il consumatore — frontend S7). Non conosce voce né UI.

## 5. Flusso (una tappa)

```
domanda(sezione) → risposta persona
   → ScopeGuard(risposta): fuori-tema/injection? → rifiuto gentile + ri-poni la domanda
   → altrimenti: estrazione vincolata → validazione Pydantic → merge nel profilo parziale
   → riepilogo della sezione → conferma?
        no/correzione → ri-estrai/aggiorna → ri-riepiloga
        sì → controllo incongruenze
              incongruenza → domanda di chiarimento gentile → ri-conferma
              ok → salva la sezione (ProfileRepository.save) + append_audit → sezione successiva
(alla fine) riepilogo finale → conferma → colloquio completato
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici** (personas varie per età/lingua/competenze/vicinanza al fine pena).
- **Unit con LLM finto** (deterministico): macchina a stati (progressione, routing conferma/correzione/chiarimento/fine); estrazione (parsing output vincolato + Pydantic + merge); guard (risposta off-topic → rifiuto + ri-poni, non avanza); persistenza per-sezione + audit; degrado (LLM giù → messaggio controllato, mai crash).
- **Integrazione con Qwen2.5 reale** (`requires_llm`): colloquio end-to-end sintetico in it/en (+ar) → profilo estratto **plausibile e solo-lavorativo**, riepilogo coerente, un'incongruenza sintetica **rilevata** e chiarita.

Priorità: la tenuta (guard non aggirato dal colloquio), il profilo solo-lavoro, la conferma-dalla-persona, le incongruenze.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| L'LLM estrae campi fuori schema | constrained decoding (json_schema) + Pydantic (extra=forbid) |
| Risposta off-topic/injection nel colloquio | `ScopeGuard` su ogni risposta; ri-poni la domanda |
| LLM lento/assente a metà colloquio | degrado elegante (messaggio controllato); sezioni confermate già salvate |
| Estrazione non deterministica nei test | LLM finto per gli unit; reale solo per l'integrazione (temp 0, asserzioni robuste) |
| Riepilogo/incongruenza che «giudica» | prompt non giudicanti (§4); test sul tono |

## 8. Criteri di accettazione

- Unit (LLM finto) verdi e deterministici: progressione, estrazione validata, guard che blocca il fuori-tema senza avanzare, persistenza per-sezione + audit, degrado senza crash.
- Con Qwen2.5 reale: un colloquio sintetico produce un `WorkProfile` **solo-lavorativo**, confermato per sezione, con un'incongruenza sintetica rilevata; nessuna fuga (PII/ambito).
- `pytest` (unit sempre; integrazione se `requires_llm`), `ruff`, `ruff format --check`, `mypy` verdi.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§4/§5/§7.1/§7.3/§9). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: aggiornato con il ciclo del colloquio e con l'esito della **validazione serving GPU** (backend Vulkan: Qwen2.5-7B Q4 in **4.76 GB VRAM**, ~38 tok/s, guardrail 7/7 su GPU — **senza CUDA toolkit**; Vulkan come opzione di deployment semplice per il kiosk).
- **Piano collegato:** scomposizione eseguibile in TDD (sottosistema coeso ma ampio → piano corposo, molte tappe).
