# STATO_TECNICO.md — Progetto «Bussola»

**Documento tecnico vivo** · Il «come» del progetto · *Ultimo aggiornamento: 2026-07-20*

---

## 0. Natura di questo documento

Questo è il **documento tecnico vivo** previsto da `CLAUDE.md` §12. Contiene il **come**: stack, modelli scelti e loro motivazione, architettura, comandi, modo di eseguire i test, decisioni operative.

- **Non è protetto.** Può evolvere liberamente man mano che il progetto avanza.
- **Non ridefinisce il cosa e il perché.** Missione, linee rosse, principi, modello del profilo, ruoli, funzionalità e criteri di successo vivono in `CLAUDE.md` (nucleo protetto, §1–§11). Se un'esigenza tecnica qui sembra contraddire il nucleo, **si applica la Regola del blocco** (§0 di `CLAUDE.md`): fermarsi, spiegare, chiedere conferma, aggiornare il nucleo solo dopo approvazione.
- **Flusso di sviluppo.** Ogni sottosistema segue: brainstorming → **spec di design** (`docs/superpowers/specs/`) → **piano di implementazione** (`docs/superpowers/plans/`) → **TDD**. La spec fissa *cosa* costruisce il sottosistema e *perché* (motivazioni delle scelte); il piano lo scompone in passi eseguibili con codice e comandi.

---

## 1. Hardware di riferimento (macchina del pilota)

Rilevato il 2026-07-20. Questa macchina (o una gemella) **è** l'hardware del pilota di Monza; il dimensionamento è pensato per starci dentro con margine.

| Componente | Dettaglio |
|---|---|
| Macchina | ASUS ROG Zephyrus G16 (GA605WI), portatile |
| OS | Ubuntu 24.04.4 LTS, kernel 6.8 |
| CPU | AMD Ryzen AI 9 HX 370 — 12 core / 24 thread, ~5.4 GHz |
| RAM | 30 GiB + 8 GiB swap |
| GPU | **NVIDIA RTX 4070 Mobile — 8 GB VRAM** (CUDA 13, driver 580) |
| iGPU | AMD Radeon 890M (integrata) |
| Disco | 972 GB (~572 GB liberi) |
| NPU | AMD XDNA 2 — **non utilizzata** (stack open su Linux ancora acerbo) |

**Il vincolo che comanda:** gli **8 GB di VRAM**. Con una sola postazione simultanea la regola d'oro è: **GPU solo per l'LLM, voce (STT/TTS) su CPU**. Nessuna contesa di VRAM, e la voce può degradare a testo senza mai bloccare il colloquio.

---

## 2. Architettura (single-box, `localhost`)

Kiosk della persona e portale operatore girano **sulla stessa macchina**, in sessioni separate. Nessun dato personale viaggia in rete: è la topologia più semplice e più sicura.

```
┌──────────────────────────────────────────────────────────────┐
│  POSTAZIONE UNICA (Ubuntu, solo 127.0.0.1)                    │
│                                                                │
│  Chromium --kiosk (persona)      Browser operatore (sessione  │
│         │                         separata, stesso box)       │
│         └──────────────┬───────────────────┘                  │
│                        ▼                                       │
│         Frontend web (React) — i18n 5 lingue, RTL arabo       │
│                        │  HTTP/WebSocket (solo 127.0.0.1)     │
│                        ▼                                       │
│              Backend applicativo (FastAPI)                    │
│    ┌───────────┬──────────────┬───────────────┬───────────┐  │
│    │ Guardrail │ Estrazione   │ Matching      │ Audit +   │  │
│    │ (ambito,  │ strutturata  │ spiegabile    │ ruoli     │  │
│    │  PII,inj) │ validata     │               │           │  │
│    └─────┬─────┴──────┬───────┴───────┬───────┴─────┬─────┘  │
│          ▼            ▼               ▼             ▼        │
│   llama.cpp       faster-whisper   Piper TTS    PostgreSQL   │
│   (LLM, GPU)      (STT, CPU)       (voce, CPU)  (segregato)  │
└──────────────────────────────────────────────────────────────┘
     GPU 8 GB ◄─ solo LLM        CPU 24 thread ◄─ tutta la voce
```

**Confine client-server pulito:** anche se oggi è tutto su un box, il backend espone un'API HTTP/WebSocket. Se in futuro il portale operatore dovesse spostarsi su una macchina in LAN, non serve riscrivere: si aggiungono solo TLS interno e segregazione di rete.

---

## 3. Stack tecnologico

| Livello | Scelta | Licenza | Dove gira |
|---|---|---|---|
| LLM | **Qwen2.5-7B-Instruct** (GGUF Q4_K_M) · fallback 3B | Apache 2.0 | GPU |
| Serving LLM | **llama.cpp** (`llama-server`, API OpenAI-compatibile) | MIT | GPU |
| STT (riconoscimento) | **faster-whisper** (CTranslate2), `large-v3-turbo` int8 | MIT | CPU |
| TTS (sintesi) | **Piper**, voci it/en/fr/es/ar | MIT | CPU |
| Filtro PII in uscita | **Presidio** (difesa in profondità) | MIT | CPU |
| Backend | **FastAPI** + Uvicorn (Python 3.12) | MIT/BSD | CPU |
| Estrazione validata | **Pydantic** + constrained decoding (GBNF/JSON-schema) | MIT | CPU/GPU |
| Frontend | **React + Vite + TypeScript**, `react-i18next` | MIT | Browser |
| Kiosk | **Chromium `--kiosk`** + utente Linux blindato | — | OS |
| Database | **PostgreSQL** (in Docker) | PostgreSQL Lic. | CPU |
| Test | **pytest** (backend), **Vitest** + **Playwright** (frontend/a11y) | MIT | — |
| Orchestrazione | **docker compose** | Apache 2.0 | — |

Tutte licenze aperte e permissive; nessun costo di licenza o servizio; nessuna API esterna per l'inferenza. Coerente con i vincoli di `CLAUDE.md` §3.

---

## 4. Modelli: scelte e motivazioni

### 4.1 LLM — Qwen2.5-7B-Instruct
- **Perché questo.** È tra i 7B multilingua più forti ed è **Apache 2.0** (permissivo, a differenza delle licenze «community» di Llama/Gemma). Eccelle su **arabo**, su **output strutturato/JSON** e sull'aderenza alle istruzioni: entrambe qualità decisive per guardrail affidabili ed estrazione conforme allo schema.
- **Quantizzazione.** GGUF **Q4_K_M** (~4.7 GB): miglior compromesso qualità/VRAM per gli 8 GB.
- **Fallback (degrado elegante).** **Qwen2.5-3B-Instruct** (~2 GB) se VRAM o latenza lo richiedono.
- **Upgrade in produzione.** Stesso serving, si cambia solo il modello: **14B** (≥12 GB VRAM) o **32B** (≥24 GB). Nessuna riscrittura.

### 4.2 STT — faster-whisper
- Whisper copre tutte e 5 le lingue **incluso l'arabo**. `faster-whisper` (backend CTranslate2) in **int8** gira veloce sui 24 thread della CPU, lasciando la GPU all'LLM.
- Default `large-v3-turbo` (equilibrio qualità/velocità); configurabile a `large-v3` per la massima qualità sull'arabo o a `small`/`medium` per più velocità.

### 4.3 TTS — Piper
- Leggero, CPU-friendly, con voci per **it/en/fr/es/ar**. Coerente con «prima il testo, la voce come potenziamento».
- **Arabo:** incluso come obiettivo; se la resa non fosse adeguata, resta garantito il **ripiego sul testo** (come da `CLAUDE.md` §8). Nessun blocco del colloquio in nessun caso.
- *Scartato:* XTTS-v2 (qualità superiore ma licenza del modello **non commerciale** → incompatibile con «licenza aperta e permissiva»).

---

## 5. Dimensionamento VRAM e degrado elegante

| In VRAM | Costo |
|---|---|
| Qwen2.5-7B Q4_K_M (pesi) | ~4.7 GB |
| KV cache (~8k token contesto) | ~1.5 GB |
| **Totale LLM** | **~6.2 GB** → sta in 8 GB con margine |
| STT + TTS | 0 GB (su CPU) |

In produzione, spostando il desktop sull'**iGPU Radeon 890M** si libera quasi tutta la VRAM NVIDIA per l'LLM.

**Livelli di degrado elegante:**
1. **Voce → testo:** se STT/TTS sono lenti o assenti, il colloquio prosegue in testo, senza interruzioni.
2. **Modello grande → leggero:** 7B → 3B se serve.
3. **Arabo:** STT pieno; TTS come obiettivo con ripiego a testo.

---

## 6. Sicurezza e privacy — come realizziamo i vincoli

La sicurezza è la **priorità n.1**. Ogni garanzia del nucleo (`CLAUDE.md` §9) ha qui una realizzazione concreta.

- **Segregazione dei dati.** Schemi PostgreSQL separati (`profiles`, `audit`; futuro `conversations`) con **ruoli DB a privilegio minimo**: `bussola_owner` (DDL/migrazioni), `bussola_app` (RW profili, **solo-INSERT** audit), `bussola_auditor` (**solo-lettura** audit). Le distinzioni tra ruoli del §6 (operatore/supervisore/amministratore) sono **RBAC applicativo** (sottosistema «Auth & operatori»), non ruoli DB.
- **Pseudonimizzazione (minimizzazione massima).** Lo **pseudonimo è l'unico identificatore** dei profili. Il sistema **non memorizza alcun dato anagrafico né la mappa pseudonimo↔persona**: quel legame vive in un **registro esterno** dell'istituto. Niente tabella di mappatura, niente `pgcrypto` per l'identità (non c'è nulla di identità da cifrare).
- **Audit immutabile.** Tabella di audit **append-only**: `UPDATE`/`DELETE` negati al ruolo applicativo (default-deny) **e** vietati da un trigger a tutti tranne l'owner. In aggiunta, **hash-chaining** (ogni record include l'hash del precedente) per rendere evidente ogni manomissione. Cintura + bretelle. *Proprietà e limiti:* è **tamper-evident** (rileva modifiche/cancellazioni post-hoc), **non tamper-proof** contro un writer `app` compromesso che inserisca una catena falsa auto-consistente → HMAC con chiave / ancoraggio esterno = **Fase 2**. Il campo `details` dell'audit è un dict libero **non** filtrato dal PII e finisce in un log non-scrubbabile: va **vincolato/sanitizzato al confine** quando gli operatori guideranno gli eventi (sottosistema Auth & portale).
- **Cifratura a riposo e in transito.** A riposo: **LUKS full-disk** sulla macchina (passo di *deployment*). In transito: tutto su `127.0.0.1` (nessun dato in rete); se in futuro si va in LAN, TLS interno. (`pgcrypto` non serve: nessun dato di identità.)
- **Guardrail (in ingresso e in uscita):**
  - **Controllo dell'ambito:** il sistema risponde solo su lavoro/formazione/orientamento; ogni richiesta fuori tema è rifiutata con garbo, sia in input sia in output.
  - **Resistenza a manipolazione (prompt injection) ed estrazione dati:** system prompt blindato, azioni consentite solo tra quelle previste, controlli indipendenti dal «buon comportamento» del modello.
  - **Filtro PII in uscita:** **Presidio** (MIT) come difesa in profondità sui testi liberi, prima di mostrare o salvare. Riconoscitori a **pattern** (email, telefono, IBAN, carta, IP) indipendenti dalla lingua e deterministici; **NER inglese** via `en_core_web_lg` (**MIT**). *Vincolo licenze (§3):* il modello NER italiano `it_core_news_lg` è **CC BY-NC-SA 3.0** (non-commerciale + copyleft), quindi **escluso**; l'italiano usa un tokenizer `spacy.blank("it")` (MIT) + i pattern. Il **NER multilingua** (nomi/luoghi per it/fr/es/ar) è un **follow-up** con un modello a licenza permissiva da verificare. La whitelist resta comunque la garanzia primaria.
  - **Garanzia strutturale primaria:** lo **schema-whitelist** del profilo (§7): per costruzione non può contenere reati, salute, dati familiari o punteggi sulla persona.
- **Postazione blindata (kiosk).** Chromium `--kiosk` sotto un utente Linux dedicato senza privilegi, scorciatoie disabilitate, nessuna navigazione libera.

---

## 7. Estrazione strutturata validata

Dalla conversazione si ricavano dati strutturati conformi a uno **schema definito**, scartando tutto ciò che non è ammesso.

- **Constrained decoding.** `llama.cpp` vincola l'output del modello a una grammatica **GBNF / JSON-schema**: il modello *non può* produrre campi fuori schema.
- **Validazione applicativa.** **Pydantic** ri-valida lato backend (doppio controllo).
- **Whitelist per costruzione.** Lo schema ammette **solo** dati lavorativi (competenze, esperienze, aspirazioni, formazione, lingue, note operative per categorie predefinite). Reati, posizione giuridica, salute, dati familiari, inferenze/valutazioni sulla persona **non sono rappresentabili**.
- **Realismo confermato dalla persona.** Il sistema riepiloga a fine sezione e a fine colloquio, chiede conferma/correzione, e sulle incongruenze pone domande gentili non giudicanti. **Chi conferma è la persona**, non l'operatore.

---

## 8. Multilingua e accessibilità

- **Lingue:** italiano, inglese, francese, spagnolo, arabo.
- **i18n:** stringhe rivolte all'utente **esternalizzate** (cataloghi), pronte per la traduzione (`CLAUDE.md` §11). Frontend con `react-i18next`; backend con cataloghi di messaggi.
- **RTL:** supporto destra-sinistra per l'arabo.
- **Accessibilità:** font grandi, alto contrasto, testo semplificato, lettura vocale, comando immediato per fermare la sessione. Verificata con test automatici (Playwright/axe).

---

## 9. Strategia di test (TDD)

Regole: **test prima del codice** (RED → GREEN → REFACTOR); **solo dati sintetici**, mai dati reali; personas sintetiche varie per età, lingua, competenze, esperienze, vicinanza al fine pena.

**Ordine di priorità (dal più importante):**
1. **Tenuta dei guardrail** — il controllo dell'ambito regge; i rifiuti sono controllati.
2. **Resistenza avversaria** — prompt injection ed estrazione dati.
3. **Nessuna fuoriuscita di dati personali** — filtro in uscita.
4. **Validatori dello schema** del profilo e **coerenza dell'estrazione**.
5. **Gestione delle incongruenze** e correttezza di **riepilogo & conferma**.

Strumenti: `pytest` (backend, guardrail e AI), `Vitest` + `Playwright` (frontend, e2e, accessibilità).

---

## 10. Struttura del repository (prevista)

> Si concretizza con il piano di implementazione; qui la forma d'insieme.

```
progetto_bussola/
├── CLAUDE.md                    # nucleo protetto (cosa/perché)
├── STATO_TECNICO.md             # questo documento (come)
├── docs/superpowers/
│   ├── specs/                   # spec di design, una per sottosistema
│   └── plans/                   # piani di implementazione (TDD), uno per sottosistema
├── backend/                     # package `bussola`: profilo, guardrail, estrazione, matching, dati
│   ├── src/bussola/
│   └── tests/                   # test (guardrail e sicurezza per primi)
├── frontend/                    # React (kiosk persona + portale operatore)
├── models/                      # modelli GGUF/whisper/piper (non versionati)
└── docker-compose.yml           # PostgreSQL + servizi
```

---

## 11. Comandi

> **Sezione viva:** cresce con l'implementazione. Stato attuale = backend del Sottosistema 1.

**Setup del backend** (da `backend/`):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_lg   # NER inglese, MIT — unico modello NER scaricato
```

> **Nota licenze/riproducibilità (§3, §10):** si scarica **solo** `en_core_web_lg` (MIT). Il modello italiano `it_core_news_lg` è **CC BY-NC-SA** e **non** va installato/usato: l'italiano è coperto dai riconoscitori a pattern + tokenizer `spacy.blank("it")`.

**Esecuzione (gate di qualità)** (da `backend/`, con `.venv` attivo):

```bash
pytest -q          # test (guardrail e sicurezza per primi)
ruff check .       # lint
mypy src           # type-check (strict)
```

---

## 12. Percorso di upgrade in produzione

Lo stack non cambia; cambiano solo le taglie:
- **LLM:** 7B → 14B (≥12 GB VRAM) → 32B (≥24 GB).
- **Concorrenza:** oltre la postazione singola, valutare un serving a più alto throughput (es. vLLM) mantenendo l'API OpenAI-compatibile.
- **Rete:** portale operatore in LAN con TLS interno e segregazione di rete (confine client-server già pronto).

---

## 13. Registro delle decisioni

| Data | Decisione | Motivo |
|---|---|---|
| 2026-07-20 | Hardware del pilota = questa macchina (8 GB VRAM) | Confermato dall'utente; dimensiono per 8 GB |
| 2026-07-20 | Topologia single-box, solo `localhost` | Confermato; più semplice e più sicuro |
| 2026-07-20 | LLM = Qwen2.5-7B-Instruct (Apache 2.0), serving llama.cpp | Migliore 7B multilingua/arabo e strutturato, licenza permissiva, controllo VRAM |
| 2026-07-20 | Voce su CPU: faster-whisper (STT) + Piper (TTS) | Nessuna contesa di VRAM; arabo con ripiego a testo |
| 2026-07-20 | Database = PostgreSQL (Docker) | Segregazione a ruoli e audit append-only imposti dal DB |
| 2026-07-20 | Frontend = React + Vite + TS | i18n/RTL maturi, accessibilità, ecosistema |
| 2026-07-20 | Flusso: spec di design **per sottosistema** prima di ogni piano | Design rivedibile a granularità di sottosistema, separato dai passi eseguibili |
| 2026-07-20 | Filtro PII: rimosso `it_core_news_lg` (CC BY-NC-SA); IT a pattern + tokenizer blank, NER EN via `en_core_web_lg` (MIT); NER multilingua permissivo = follow-up | §3: solo licenze permissive; §10: donabile e replicabile |
| 2026-07-21 | Sott. 2: nessun dato identità nel sistema (mappa pseudonimo↔persona esterna); psycopg3 + migrazioni SQL; ruoli DB coarse (owner/app/auditor) + RBAC app; profilo JSONB; sanitize al salvataggio | Minimizzazione (§4/§5); trasparenza del DDL di sicurezza (§9); filtro in uscita (§7.3) |
| 2026-07-21 | Inserito sottosistema «Auth & operatori» (account, autenticazione, RBAC) prima del portale operatore | Operatore = principal autenticato; persona detenuta = solo pseudonimo, senza account |
| 2026-07-21 | Driver DB = `psycopg3` (LGPL-3.0), accettato come interpretazione larga di §3 | LGPL a link dinamico: nessun obbligo sul nostro codice, donation/commercial-friendly. Restano ESCLUSI copyleft forte (GPL) e non-commerciale (es. CC BY-NC). |

---

## 14. Debito tecnico e follow-up noti

Registrati dalle revisioni (nessuno bloccante; da affrontare al momento giusto):

- **Audit `details` → vincolare/sanitizzare** al confine degli eventi operatore (sottosistema Auth & portale): oggi è un dict libero non filtrato in un log immutabile.
- **Hash-chain → HMAC con chiave / ancoraggio esterno** (Fase 2) per resistere a un writer compromesso (oggi tamper-evident, non tamper-proof).
- **Transazione unità-di-lavoro** per il portale: oggi `ProfileRepository` e `append_audit` committano separatamente; per «nessuna azione senza il suo record di audit» servirà una transazione condivisa.
- **`ruff format --check` nel gate** + riformattare 2 file pre-esistenti del Sott. 1 (`pii.py`, `test_sanitize_profile.py`) in un commit di housekeeping.
- **`db-init/00-roles.sh`**: le password sono interpolate come literal SQL (init una-tantum, input del deployer) → avvertenza «niente apici singoli» o binding.
- **Test aggiuntivi (hardening):** idempotenza del runner di migrazioni (`[]` alla 2ª esecuzione); percorso fail-closed di `ProfileRepository.save` end-to-end; `details` con payload non banale per la hash-chain (normalizzazione numeri JSON).
- **`_CHAIN_LOCK_KEY`**: documentare uno schema di namespacing per gli advisory-lock (sono cluster-wide).
