# Spec di design — Sottosistema 1: Fondamenta, modello del profilo e filtro PII

**Progetto «Bussola»** · Sottosistema 1 di 8 · *Design di riferimento per il [Piano 1](../plans/2026-07-20-fondamenta-profilo-e-filtro-pii.md)* · 2026-07-20

---

## 0. Cos'è questo documento

È la **spec di design** del primo sottosistema, secondo il flusso di sviluppo adottato:

> brainstorming → **spec di design (questo file)** → piano di implementazione → TDD.

Sta a un'altitudine di **design**: descrive *cosa* costruiamo in questo sottosistema e *perché* ogni scelta, con le motivazioni. Non contiene codice né passi operativi: quelli vivono nel piano collegato. Deriva e raffina, per questo sottosistema, ciò che `CLAUDE.md` §5/§7.3 (funzionale) e `STATO_TECNICO.md` §6-7 (tecnico) già fissano.

Ogni sottosistema successivo avrà la propria spec in `docs/superpowers/specs/` prima del proprio piano.

---

## 1. Contesto e scopo

Il sottosistema realizza le **fondamenta strutturali di sicurezza** del sistema: il **modello del profilo lavorativo** e il **filtro dei dati personali in uscita**. È il primo perché è ciò su cui poggia tutto il resto (estrazione, persistenza, matching) ed è la garanzia che rende sicuro l'accesso degli operatori (`CLAUDE.md` §2): *il profilo, per costruzione, non può contenere materiale sensibile*.

È logica pura: nessun LLM, nessun database, nessuna rete. Quindi i test sono **deterministici e veloci**, ideali per avviare il TDD.

## 2. Obiettivi e non-obiettivi

**Obiettivi (in questo sottosistema):**
- Package backend `bussola` con ambiente e test funzionanti.
- Schema del profilo lavorativo come **whitelist**: rappresenta solo dati lavorativi e **rifiuta per costruzione** qualsiasi campo non pertinente.
- Validazione rigorosa (Pydantic) con rifiuto dei campi ignoti a ogni livello.
- **Filtro PII in uscita** come seconda linea di difesa sui campi a testo libero.

**Non-obiettivi (rimandati, con destinazione):**
- **Persistenza** del profilo (PostgreSQL, segregazione, audit, cifratura) → Sottosistema 2.
- **Guardrail comportamentali** (controllo ambito, injection) e **filtro semantico dei temi vietati** dentro il testo libero (es. accenni a reati/salute) → Sottosistemi 3-4, dove c'è l'LLM.
- **NER PII per fr/es/ar** → esteso più avanti (qui: NER it/en; i pattern email/telefono/IBAN sono già indipendenti dalla lingua).
- **Riepilogo & conferma, incongruenze** → Sottosistema 4.

## 3. Decisioni di design (con motivazione)

1. **Profilo come whitelist Pydantic con `extra="forbid"`.**
   *Perché:* è la garanzia **strutturale** richiesta da `CLAUDE.md` §2/§7.3. Non dipende dal buon comportamento del modello: se un campo non lavorativo non esiste nello schema e i campi ignoti sono rifiutati, quel dato *non è rappresentabile*. La sicurezza è nella struttura, non in un controllo a runtime aggirabile.

2. **Enum chiusi dove i valori sono predefiniti.**
   *Perché:* ogni campo a testo libero è una superficie di rischio (può ospitare dati sensibili). Dove il dominio è finito (livelli di lingua, alfabetizzazione digitale, grado di evidenza, categorie di note operative) usiamo enum chiusi. In particolare le **note operative** sono **solo categorie predefinite** (`CLAUDE.md` §5): niente testo libero.

3. **`Availability` e `WorkConstraint` deliberatamente privi di campi giuridici o sanitari.**
   *Perché:* è una **linea rossa** (`CLAUDE.md` §2). «Disponibilità» resta pianificazione del lavoro (tempo pieno/parziale/flessibile), **non** regime giuridico (es. se il lavoro esterno è legalmente ammesso). «Vincoli» restano di pianificazione/formazione, **non** limitazioni fisiche o sanitarie. Questa esclusione è una scelta di design esplicita, annotata nel codice.

4. **Difesa a due livelli: whitelist (primaria) + redazione PII (ridondanza).**
   *Perché:* `CLAUDE.md` §7.3 chiede che «il modello non decida da solo cosa esporre». La whitelist garantisce *quali campi* esistono; il filtro PII garantisce che *dentro i campi liberi* non finiscano dati personali (nomi, contatti). Cintura + bretelle.

5. **Filtro PII con Presidio: pattern indipendenti dalla lingua + NER it/en.**
   *Perché:* email/telefono/IBAN/carta sono riconosciuti da pattern deterministici, validi in ogni lingua. Nomi/luoghi richiedono NER (spaCy), qui configurato per it+en. Le entità rilevate sono sostituite da segnaposto (`<PERSON>`, `<EMAIL_ADDRESS>`). L'estensione a fr/es/ar è rimandata (vedi §2).

6. **`sanitize_profile` non muta l'originale.**
   *Perché:* prevedibilità e sicurezza. Ritorna una copia profonda redatta; l'oggetto d'ingresso resta invariato, così il chiamante decide esplicitamente cosa salvare/mostrare.

## 4. Unità e confini

Due moduli a responsabilità singola, con confini netti:

- **`bussola.profile`** — *il modello dei dati.*
  - `enums.py`: enumerazioni chiuse.
  - `models.py`: modelli foglia (`LanguageKnown`, `Skill`, `WorkExperience`, `Aspiration`, `DesiredTraining`) e aggregato (`WorkProfile`).
  - *Dipende da:* solo Pydantic. *Usato da:* estrazione, persistenza, matching (piani futuri).

- **`bussola.guardrails`** — *le difese.*
  - `pii.py`: `PiiRedactor` (redazione di un testo) e `sanitize_profile` (redazione di un profilo).
  - *Dipende da:* Presidio/spaCy e da `bussola.profile.models`. *Usato da:* ogni punto che salva o mostra un profilo (piani futuri).

Criterio di isolamento: si può capire cosa fa ogni unità senza leggerne l'interno, e cambiarne l'interno senza rompere i consumatori.

## 5. Modello dati (forma concettuale)

`WorkProfile` (mappa su `CLAUDE.md` §5):

| Campo | Tipo | Note |
|---|---|---|
| `pseudonym_id` | stringa | identificativo interno pseudonimizzato |
| `languages` | lista di `LanguageKnown` | lingua + livello |
| `digital_literacy` | enum \| assente | alfabetizzazione digitale |
| `skills` | lista di `Skill` | nome + tipo (tecnica/trasversale) + grado di evidenza |
| `experiences` | lista di `WorkExperience` | ruolo + settore + durata (mesi) |
| `aspiration` | `Aspiration` \| assente | ambiti d'interesse + disponibilità + vincoli |
| `desired_training` | lista di `DesiredTraining` | temi di formazione desiderati |
| `operational_notes` | lista di enum | **solo categorie predefinite** |

**Non contiene, per costruzione:** reati, posizione giuridica, pericolosità; dati sanitari; dati familiari/personali non pertinenti; inferenze, valutazioni o punteggi sulla persona.

**Campi a testo libero** (soggetti a redazione PII): `skill.name`, `experience.role`, `experience.sector`, `aspiration.fields_of_interest[]`, `desired_training[].topic`.

## 6. Strategia di test (priorità: sicurezza)

TDD, **solo dati sintetici**. Ordine di importanza:
1. **Garanzia whitelist** — il profilo rifiuta i campi vietati (reati, salute, famiglia, punteggi) e le note a testo libero. *Sono i test di sicurezza centrali del sottosistema.*
2. **Redazione PII** — email/telefono/nomi redatti; testo senza PII invariato; originale non mutato.
3. **Validazione dei modelli foglia** — vincoli e rifiuto dei campi ignoti.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| NER non deterministico al 100% | Test su casi robusti; la base deterministica sono i pattern (email/telefono) |
| NER arabo limitato in spaCy | Pattern attivi comunque; NER ar rimandato con riconoscitore alternativo |
| Modelli spaCy `lg` pesanti (~500 MB) | Disco abbondante; opzione `sm` se serve leggerezza |
| `mypy --strict` su dipendenze senza stub | `ignore_missing_imports` mirato per Presidio/spaCy |

## 8. Criteri di accettazione

- Tutti i test della whitelist passano (inclusi i campi vietati parametrizzati).
- La redazione PII funziona su it/en per email, telefono e nomi; il testo senza PII resta invariato.
- `sanitize_profile` non muta l'originale.
- `pytest`, `ruff check`, `mypy` verdi.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): il *cosa/perché* funzionale — questa spec vi si conforma, non lo ridefinisce.
- **`STATO_TECNICO.md`** (tecnico vivo): stack e architettura d'insieme.
- **[Piano 1](../plans/2026-07-20-fondamenta-profilo-e-filtro-pii.md)**: la scomposizione eseguibile, passo-passo, di questo design.
