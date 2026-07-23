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
  - **Controllo dell'ambito:** il sistema risponde solo su lavoro/formazione/orientamento; ogni richiesta fuori tema è rifiutata con garbo, sia in input sia in output. Realizzato (Sott. 3) con un **guard layer indipendente**: guard di **input** = classificatore LLM strutturato (`{allow, category, reason}`, temp 0) + validazioni deterministiche; guard di **output** = ri-check di ambito via LLM **sempre attivo** (§2 «in uscita») + filtro PII + controlli anti-fuga. Rifiuti **strutturati** con messaggio localizzato non giudicante. Serving: **`llama-server` nativo** (CUDA), client httpx sull'endpoint OpenAI-compatibile.
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

**Serving LLM (llama-server, OpenAI-compatibile).**

Prerequisito: un binario `llama-server` con accelerazione GPU sul `PATH`. Due vie:
- **Vulkan (validato, consigliato):** release prebuilt `bin-ubuntu-vulkan` di llama.cpp — usa la GPU NVIDIA via il driver, **nessun CUDA toolkit, nessuna build da sorgente**. Requisiti già presenti qui: `libvulkan.so.1` + ICD NVIDIA (`nvidia_icd.json`, dal driver 580).
- **CUDA:** build da sorgente con `-DGGML_CUDA=ON` (richiede CUDA toolkit/`nvcc`) — potenzialmente più veloce; **non** esiste un prebuilt CUDA per Linux.

**Validazione serving (2026-07-21, backend Vulkan, RTX 4070 Mobile 8 GB):** Qwen2.5-7B Q4_K_M usa **~4.76 GB di VRAM** (entra negli 8 GB con margine), latenza a caldo **~38 token/s**, suite avversaria dei guardrail **7/7** su GPU. Vulkan è quindi un'opzione di deployment semplice e sufficiente per il kiosk.

```bash
bash scripts/serve-llm.sh   # scarica il modello (una tantum, ~4.7 GB) e avvia il server su :8080
```

Lo script scarica i due shard del Q4_K_M ufficiale di Qwen2.5-7B-Instruct-GGUF in `models/`
(se non già presenti) e avvia `llama-server` puntato sul primo shard, con offload GPU
(`-ngl 999`) e contesto 8192. `models/` è in `.gitignore`: i pesi non vengono mai versionati.

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
- **Sott. 4 — `output ScopeGuard` sui testi generati** (`check_output`, una chiamata LLM): non ancora applicato ai riepiloghi/chiarimenti (il filtro PII sì). Rischio basso (dati solo-lavoro, stessa sessione/persona); da chiudere quando S7 renderizza le stringhe.
- **Sott. 4 — grado di evidenza ottimistico:** col modello reale una competenza solo *dichiarata* può essere estratta come `evidence="certified"`; candidato a tuning del prompt d'estrazione (non un difetto strutturale).
- **Sott. 4 — copertura test minori:** wiring dell'`audit` hook non esercitato dai test (kwargs allineati a S2 ma non verificati end-to-end); ramo di rifiuto nella clarification finale non testato a livello unit; docstring `extraction.py` («unparseable/invalid») da precisare a «invalid (schema)».
- **Sott. 4 — `submit()` dopo `completed`** restituisce «unavailable» (messaggio fuorviante): valutare uno Step terminale dedicato.
- **Sott. 4 — `_final_summary`**: stringhe i18n inline nell'orchestratore; valutare di centralizzarle nel modulo messaggi (coerenza §11).
- **Sott. 5 — `must_change_password` non forzato come gate**: un operatore che deve cambiare password può chiamare altri endpoint prima di farlo → aggiungere il gate nel **sottosistema portale** (ora impatto basso: nessun endpoint di business esiste ancora, la temp password è ad alta entropia).
- **Sott. 5 — stringhe d'errore API i18n**: i messaggi in `api/errors.py` sono in italiano inline; esternalizzare quando arriva il frontend (S7).
- **Sott. 5 — `create_operator` rollback difensivo**: su `UniqueViolation` la transazione resta aborted; oggi innocuo perché `get_conn` chiude la connessione per-richiesta, ma introdurre un rollback al confine API prima di adottare un connection-pool.
- **Sott. 5 — `role text` senza CHECK a DB**; **catch `UniqueViolation` generico**; **`_fail` non `NoReturn`**; **`action: str` non `Literal`**; **`bootstrap.main()` senza test** + TOCTOU check-then-act su bootstrap concorrente (script run-once): hardening minori di S5 da valutare.
- **Sott. 5 — convenzione migrazioni**: `0004_auth.sql` crea schema+tabelle nello stesso file (0001 centralizzava gli schema). Convenzione (schema-per-file vs schema-upfront) da fissare qui.
- **Sott. 5 — test aggiuntivi**: idle-timeout di sessione in isolamento; asserzione del code-path `dummy_verify` (oltre a status/messaggio); fault-injection sul rollback atomico stato+audit.
- **Sott. 6 — grounding dell'evidenza enforced solo via prompt + test d'integrazione**: un check codice (substring dell'evidenza nel profilo) rifiuterebbe evidenze legittimamente parafrasate/tradotte (danneggia il recall) → non adottato; valutare in Fase 2 un ancoraggio più sofisticato (es. verifica per-skill).
- **Sott. 6 — follow-on del portale**: **metriche minime** e **export di base con autorizzazione** (§7.2/§7.3), **persistenza/storicizzazione degli esiti di matching** (Fase 2), **peso per grado di evidenza** nello scoring (ora frazione soddisfatta).
- **Sott. 6 — degrado**: `LlmUnavailable → 503` gestito; un errore LLM non-transport (es. HTTP 5xx del server → `HTTPStatusError`) resta 500 (comportamento S3 pre-esistente) — valutare una mappatura dedicata.
- **Sott. 6 — test minori**: ordine di ranking (con survivor a punteggi diversi), branch `search(language=)`/filtri combinati, wording duplicato dei motivi quando entrambi i segnali part-time scattano.

---

## 15. Registro delle decisioni (segue)

| Data | Decisione | Motivo |
|---|---|---|
| 2026-07-21 | Sott. 3: guard layer **indipendente** (guard input = classificatore LLM strutturato temp 0; guard output = ri-check ambito LLM **sempre attivo** + filtro PII) | §2 ambito in ingresso **e in uscita**; §7.3 controlli indipendenti dal buon comportamento del modello |
| 2026-07-21 | Sott. 3: serving `llama-server` **nativo** (CUDA), client **httpx** verso endpoint OpenAI-compatibile; modello Qwen2.5-7B GGUF Q4 (Apache 2.0) | Toolkit GPU per Docker assente → GPU nativa più semplice; dipendenze minime; nessuna API esterna |
| 2026-07-21 | Serving GPU **validato via Vulkan** (prebuilt, no CUDA toolkit): VRAM ~4.76 GB, ~38 tok/s, guardrail 7/7 su GPU. Vulkan = opzione di deployment del kiosk | Nessun prebuilt CUDA Linux; Vulkan usa la GPU col solo driver → più semplice/replicabile (§10) |
| 2026-07-21 | Sott. 4 (colloquio): flusso **deterministico** guidato dall'app; estrazione **per-sezione con constrained decoding**; incongruenze via **LLM semantico**; riepilogo & conferma **dalla persona**; stato in-memory + persistenza per-sezione | §7.1 «il sistema conduce»; §7.3 estrazione validata; §5 validazione con la persona; ripresa a metà sezione = Fase 2 |
| 2026-07-23 | Sott. 4 concluso + validato end-to-end con Qwen2.5-7B reale su GPU (Vulkan) + Postgres. Estrazione vincolata **eccellente**; validazione reale ha corretto 2 comportamenti del modello (vedi §14/remediation): incongruenze **a fine colloquio** (prompt rigoroso, mai campi mancanti) e **precisione dello scope-guard** (esempi in-ambito, no falso «lingua diversa»), guard avversario **7/7** riverificato | Il metro è «si comporta come promesso quando messo alla prova» (§10): il test live ha fatto emergere difetti che asserzioni deboli avrebbero nascosto |
| 2026-07-23 | Sott. 4: **filtro PII in uscita anche «prima di mostrare»** — `PiiRedactor` (Presidio, no LLM) applicato ai testi generati (riepilogo/chiarimento) nell'orchestratore, oltre al filtro già presente a persistenza | Nucleo §7.3 richiede il filtro «prima di mostrare **o** salvare»; rilevato dalla review finale opus |
| 2026-07-23 | Sott. 5 «Auth & operatori»: **autenticazione a password (argon2id) + sessioni server-side + RBAC + primo layer HTTP (FastAPI)**. Sessioni: token opaco, in DB solo l'hash SHA-256, scadenza assoluta+idle, revoca immediata. Account provisionati **solo dall'Amministratore** (no self-signup), bootstrap CLI senza credenziali di default. Login: errore generico + dummy-verify (no user-enumeration) + lockout. Ogni evento auth **auditato e atomico** (`append_audit(commit=False)` + un solo commit del servizio) con `details` whitelist. Deps nuove permissive: fastapi (MIT), uvicorn (BSD), argon2-cffi (MIT) | §6 ruoli/privilegio minimo; §7.2 utenza autorizzata dalla Direzione; §7.3 audit immutabile senza fughe; §3 open-source permissivo, prevenzione abusi. Review finale opus: nessun bypass/fuga; Ship with follow-ups |
| 2026-07-23 | Sott. 5: `append_audit` acquisisce `commit: bool = True` (default invariato per S2) → gli eventi auth partecipano alla **transazione unità-di-lavoro** del chiamante | Chiude i follow-up S2 «details da vincolare al confine operatore» e «transazione unità-di-lavoro» per gli eventi auth (§7.3: nessuna azione senza il suo record) |
| 2026-07-23 | Sott. 6 «Portale operatore — core matching»: **matching ibrido** = gate deterministico dei vincoli rigidi (disponibilità/turni-notturni/livello-lingua, enum) che esclude con motivo PRIMA dell'LLM + giudizio semantico LLM **ancorato** sul testo libero (per requisito: soddisfatto/no + evidenza citata dal profilo, constrained JSON, temp 0, fail-safe non-soddisfatto). Scoring = frazione soddisfatta (trasparente); gap → formazione consigliata. Richieste di lavoro (schema `matching`), ricerca profili (JSONB), endpoint operatore RBAC (attiva i permessi §6) + audit; matching on-demand, non persistito. Validato end-to-end con Qwen2.5-7B reale su GPU | §2 «mai una scatola nera» + §10 «matching spiegabile con gap»: spiegabile per costruzione senza tassonomia da mantenere; i vincoli non-negoziabili restano deterministici e non «ragionabili via» dal modello. Review finale opus: nessun giudizio sulla persona/rischio, no PII leak; Ship with follow-ups |
| 2026-07-23 | Sott. 6: nessuna tassonomia di competenze da mantenere — il matching semantico è affidato all'LLM locale (già disponibile, costo marginale zero) con output ancorato; alternativa scartata: tassonomia controllata (es. ESCO) che richiederebbe comunque un LLM per classificare il testo libero + manutenzione | Decisione di prodotto (utente): i profili sono testo libero in 5 lingue; un confronto per stringhe fallisce, e mantenere categorie è oneroso. L'ancoraggio + il gate deterministico preservano il §2 |
