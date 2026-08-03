# Recap finale schematico + chiarimento aperto sull'ambiguità — Design

**Progetto Bussola** · Sottosistema colloquio (§5/§7.1) · 2026-08-03

## Contesto e governance

Dall'uso reale è emerso che un'estrazione può essere silenziosamente sbagliata
(«ho lavorato come consulente» → ruolo «lavorato») e che manca un momento in cui
la persona verifichi **l'intero** profilo e in cui il sistema chieda conferma
**con una domanda aperta** quando qualcosa non è chiaro.

Questo design **realizza** ciò che il nucleo già prescrive — **non lo modifica**:

- **§5:** «il sistema riepiloga ciò che ha compreso — al termine di ogni sezione
  e **alla fine del colloquio** — e chiede alla persona di **confermare o
  correggere**; quando emerge un'**incongruenza** … pone una **domanda di
  chiarimento gentile**».
- **§7.1:** «Riepilogo e conferma dalla persona … alla fine di ogni sezione e del
  colloquio»; «Chiarimento delle incongruenze … una domanda gentile».

Nessun dato nuovo nel profilo, nessun cambio di ruoli/linee rosse. §4 resta il
vincolo guida (domande brevi, voce, bassa alfabetizzazione, degrado elegante).

## Obiettivi

1. La persona può **verificare l'intero profilo** alla fine, in forma schematica
   (come lo vede l'operatore) e **correggerlo a voce/testo libero**.
2. Quando un'estrazione è **ambigua o incoerente** con quanto detto prima, il
   sistema pone **una domanda aperta gentile** invece di procedere in silenzio —
   ma **solo** quando serve, per non allungare il colloquio (§4).

## Non-obiettivi

- Non si aggiunge una domanda aperta di verifica su *ogni* risposta (friction §4).
- Non si tocca lo schema del profilo né i ruoli/RBAC.
- La revisione con madrelingua delle stringhe (incl. arabo) resta un follow-up
  già noto, fuori da questa spec.

## Architettura: tre reti complementari

Dal più economico/precoce al più completo:

1. **Chiarimento aperto per-sezione** — cattura presto l'ambiguità intra-sezione
   e l'incoerenza con le sezioni già confermate.
2. **Controllo di incongruenza a fine colloquio** — `find_incongruence`, **già
   esistente**, invariato: ultima rete sulle contraddizioni cross-sezione che
   emergono solo a profilo completo.
3. **Recap finale schematico** — la verifica finale della **persona** su tutto.

Le tre non sono ridondanti: (1) è per-sezione e forward, (2) è cross-sezione a
fine, (3) è la conferma umana esplicita su tutto.

---

## Componente 1 — Chiarimento aperto per-sezione

**Nuova funzione** (in `bussola/interview/incongruence.py` o nuovo
`clarify.py`):

```
find_section_clarification(
    client: LlmClient, section: Section, extracted: BaseModel,
    profile: WorkProfile, language: str
) -> str | None
```

Una chiamata `chat_json` (temp 0) che, dato **l'estrazione della sezione** e il
**profilo finora**, restituisce una domanda aperta gentile **se e solo se**:
- un campo chiave è ambiguo/malformato (es. un `role` che è un verbo generico
  come «lavorato», una durata che non torna), **oppure**
- l'estrazione è **incoerente** con una sezione precedente (§5 «coerenza con i
  lavori del punto precedente»).

Altrimenti `None`. Schema di ritorno: `{needs_clarification: bool, question: str}`.
La domanda è **nella lingua scelta** (regola lingua come in `summarize`), senza
emoji, in parole semplici (§4).

**Integrazione nel flusso** (`Interview`, `interview.py`):

- Nuovo stato `_awaiting_section_clarification: bool` e `_section_clarification:
  str | None`.
- Percorso «risposta normale» (oggi: guard → `_section_answer = answer` →
  `_summarize_section`): **inserire** dopo l'estrazione, **prima** del riepilogo,
  la chiamata a `find_section_clarification`.
  - Se restituisce una domanda → `_awaiting_section_clarification = True`;
    ritorna `Step("clarification", _present(question))` (guardia in uscita +
    PII come ogni testo generato). **Nessuna** estrazione persa: `_section_answer`
    conserva la risposta.
  - Se `None` → riepilogo, come oggi.
- Percorso «rispondo alla clarification di sezione» (`_awaiting_section_clarification`):
  guard (giudicato **contro la domanda di chiarimento**, come già si fa per la
  correzione contro il riepilogo) → `_section_answer = f"{_section_answer}\n{reply}"`
  → **ri-estrazione dal testo completo** → **si va dritti al riepilogo**
  (nessun secondo controllo di chiarezza: **max una domanda aperta per sezione**,
  §4). Reset del flag.

**Degrado (§3):** se la chiamata di chiarezza fallisce (LLM giù/timeout), si
**salta** il chiarimento e si procede al riepilogo (fail-open: è una rete
aggiuntiva, non deve bloccare il turno). Il `try/except` di `submit` resta la
rete finale per gli altri errori.

**Costo:** +1 chiamata LLM per sezione (breve, temp 0); la domanda si mostra solo
quando serve. Le altre reti restano.

---

## Componente 2 — Recap finale schematico

### Generazione (backend, SENZA LLM)

Il recap è la **resa del profilo già salvato** — quindi non serve l'LLM per
comporlo, né una nuova passata di guardia in uscita: i dati sono già stati
filtrati PII a ogni `save` di sezione, e sono le parole della persona.

- Nuovo stato `_awaiting_recap: bool`.
- Dopo che tutte le sezioni sono confermate **e** il controllo `find_incongruence`
  finale è ok (oggi `_finalize` → `_complete`): invece di completare subito, si
  entra nel recap → `_awaiting_recap = True`; ritorna `Step("recap", "", recap=profile)`.
- Il testo di intro breve (es. «Ecco cosa ho capito. Controlla che sia giusto.»)
  è una stringa **statica** per lingua (come `_final_summary`), non generata.

### Contratto `Step` / API

- `Step` (dataclass, `interview.py`) e `StepOut` (API, `kiosk/routers/interview.py`)
  guadagnano un campo **opzionale** `recap: WorkProfile | None = None`.
  Popolato **solo** quando `kind == "recap"`; gli altri kind invariati (`text`
  resta l'intro). Si **riusa `WorkProfile`** come payload (è il profilo della
  persona; il kiosk non renderizza `pseudonym_id`).

### Resa (kiosk)

- Nuovo `Screen` **`recap`** e componente `Recap.tsx`: rende `step.recap` come
  **lista a etichette** a sezioni, font grande/contrasto (§4):
  - Competenze (nome — tipo — evidenza), Lingue (lingua — livello),
    Alfabetizzazione digitale, Esperienze (**ruolo — settore — durata**),
    Aspirazioni/Interessi, Formazione desiderata, Disponibilità e Vincoli, Note.
  - I **valori enum** (livelli, tipo competenza, evidenza, disponibilità,
    vincoli, note, alfabetizzazione) sono resi con **nuove etichette i18n nelle
    5 lingue** (le stringhe libere — nome competenza, ruolo, settore, topic —
    sono mostrate come sono, parole della persona).
  - La **VoiceBar legge** un testo **composto lato kiosk** dalle stesse
    etichette+valori (nessun LLM).
- Due azioni: **«È tutto giusto»** (conferma) e **«Correggi»** (apre input
  voce/testo, riusando il pattern di `ConfirmCorrect`).
- Reducer kiosk: `case 'recap'` mappa a schermata `recap`; conferma/correzione
  passano da `submit` come oggi.

### Correzione del recap (l'unico punto “intelligente”)

Sul `submit` mentre `_awaiting_recap`:
- `interpret_confirmation(reply)` → se **confermato** → `_complete()`
  (completato). Riusa l'interpretazione conferma esistente.
- altrimenti è una **correzione a testo libero**:
  1. **guard** di scope sulla risposta (giudicata contro il recap);
  2. **routing + ri-estrazione** — nuova `apply_recap_correction(client, reply,
     profile, language) -> (section_key, BaseModel)`: l'LLM (a) individua **quale
     sezione** riguarda la correzione e (b) produce, con **decoding vincolato**
     sullo schema di **quella** sezione, l'estrazione corretta dati il contenuto
     **attuale** di quella sezione + la correzione (es. esperienze attuali +
     «il consulente era 2 anni» → esperienze corrette);
  3. `session.merge(extracted)` (semantica first-interview: sovrascrive quella
     sezione) → `repo.save` (filtro PII) → **ri-mostra** il recap aggiornato.
- La persona può correggere più volte; conferma quando è soddisfatta (nessun cap).

**Rischio dichiarato (da validare live, §10):** il routing della correzione dal
testo libero alla sezione giusta è l'unico punto che dipende dal giudizio
dell'LLM. Fallback (§3): se il routing/ri-estrazione fallisce o non individua una
sezione, si mostra un messaggio gentile «non ho capito la correzione, puoi
ridirla?» e si resta sul recap (non si perde nulla, non si completa).

---

## Componente 3 — Incongruenza a fine colloquio (invariata)

`find_incongruence` resta come oggi: gira una volta a fine colloquio, prima del
recap; se trova una contraddizione pone una clarification aperta; la risposta la
si giudica e si completa (Fase 1). Il recap arriva **dopo** che questa è ok.

---

## Flusso (sequenza)

```
… risposta di sezione
  → guard → estrazione
  → find_section_clarification?
      sì → Step(clarification) → risposta → append → ri-estrazione → riepilogo
      no → riepilogo (sì/no)
  → conferma → save → avanza
… tutte le sezioni confermate
  → find_incongruence (esistente)? sì → clarification finale → risposta
  → Step(recap, recap=profile)
      «è giusto» → completato
      correzione → routing+ri-estrazione → save → Step(recap, …) [ripete]
```

## Gestione errori / degrado (§3)

- Chiarezza per-sezione fallita → si salta (fail-open), si va al riepilogo.
- Recap: nessun LLM in generazione → nessun nuovo modo di fallire; se manca la
  voce, il testo/lista restano (degrado voce→testo già previsto).
- Correzione recap fallita/non instradabile → messaggio gentile, si resta sul
  recap. `submit` mantiene il `try/except → unavailable` per il resto.

## Testing (§9)

Unit (doppie LLM deterministiche, come i test colloquio esistenti):
- chiarezza scatta su ambiguità (ruolo=verbo, incoerenza con sezione precedente)
  e **non** su risposta chiara; **max una** domanda per sezione; la risposta si
  accumula e la sezione **non** viene ri-chiesta da capo.
- degrado: chiarezza LLM giù → si procede al riepilogo (nessun blocco).
- recap: lo `Step` porta il profilo; conferma → completato; correzione a voce →
  instradata alla sezione giusta, ri-estratta, salvata, recap ri-mostrato;
  routing fallito → resta sul recap con messaggio.
- kiosk: reducer `recap`; `Recap.tsx` rende le sezioni + etichette 5 lingue; la
  VoiceBar legge il testo composto; a11y (axe) del nuovo schermo.
Live (`@pytest.mark`… come i test live esistenti, il metro §10): con LLM reale,
«consulente» non diventa «lavorato» o viene chiesto un chiarimento; il recap
mostra il profilo; una correzione a voce aggiorna il campo giusto.

## Ambito

Fase 1. Fuori: revisione madrelingua delle nuove stringhe (incl. arabo) e voce
araba (follow-up §14 già noti); una domanda aperta di verifica su *ogni* risposta
(esclusa per §4).
