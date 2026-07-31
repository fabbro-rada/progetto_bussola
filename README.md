# Bussola

**Assistente per la profilazione lavorativa delle persone detenute** — progetto pilota, Casa Circondariale di Monza.

Bussola è un assistente conversazionale che **funziona interamente in locale** e aiuta ogni persona detenuta a costruire un **profilo lavorativo realistico** (esperienze, competenze, aspirazioni, bisogni formativi), permettendo agli operatori di orientarla e collegarla a **opportunità di lavoro reali**. È un uso dell'IA mirato al **reinserimento sociale attraverso il lavoro** — non al controllo, alla sorveglianza o alla previsione del rischio.

- **Locale e a costo zero:** modelli e dati vivono su infrastruttura interna; nessun servizio cloud, nessuna API esterna, nessun costo di licenza.
- **Multilingua e vocale:** cinque lingue (italiano, inglese, francese, spagnolo, arabo) con voce, perché a Monza quasi metà della popolazione è straniera. Il testo funziona sempre; la voce è un potenziamento con **degrado elegante** verso il testo.
- **Profilo minimo per costruzione:** contiene *solo* dati lavorativi. Per costruzione **non** può contenere reati, dati sanitari o dati familiari sensibili.

> **Che cosa Bussola NON è:** non è uno strumento di sorveglianza, controllo o disciplina; non stima pericolosità né calcola punteggi sulle persone; i dati non sono riusabili per finalità di sicurezza o valutazione. Le linee rosse complete sono in [`CLAUDE.md`](CLAUDE.md) §2.

Per il **cosa e perché** (missione, principi, ambito) vedi [`CLAUDE.md`](CLAUDE.md); per il **come** (stack, modelli, decisioni tecniche) vedi [`STATO_TECNICO.md`](STATO_TECNICO.md); per licenze e attribuzioni [`CREDITS.md`](CREDITS.md).

---

## Architettura in breve

Tutto gira su una singola macchina, su `localhost` (topologia single-box, senza esposizione esterna):

| Componente | Cosa fa | Tecnologia | Porta (dev) |
|---|---|---|---|
| **Backend** | API, colloquio, estrazione validata, guardrail, matching, audit | Python 3.12 · FastAPI · psycopg3 | `8000` |
| **Kiosk** | App rivolta alla persona detenuta (colloquio guidato, voce, multilingua) | React 18 · Vite · TypeScript | `5173` |
| **Portale operatore** | Richieste di lavoro, matching spiegabile, profili, metriche, export, audit | React 18 · Vite · TypeScript | `5174` |
| **Database** | Profili, sessioni, log di audit (append-only) | PostgreSQL 16 (Docker) | `5432` |
| **LLM** | Motore del dialogo e dell'estrazione | llama-server (Qwen2.5-7B-Instruct, GGUF) | `8080` |
| **Voce** | STT (riconoscimento) e TTS (lettura ad alta voce) | faster-whisper · Piper | in-process |

---

## Prerequisiti

- **[uv](https://docs.astral.sh/uv/)** — gestore di Python e dipendenze del backend (`curl -LsSf https://astral.sh/uv/install.sh | sh`). Fornisce lui stesso **Python 3.12** (fissato da `backend/.python-version`), quindi non serve installare Python a mano.
- **Node.js 18+** e npm
- **Docker** + il **plugin Docker Compose v2** (`docker compose`) — su Ubuntu: `sudo apt-get install docker-compose-v2`; verifica con `docker compose version`. (In alternativa va bene anche `docker-compose` v1: gli script rilevano automaticamente quale è presente.)
- Per il **colloquio** (LLM): una GPU (~8 GB VRAM) e un binario **`llama-server`** con accelerazione GPU sul `PATH`. La via consigliata e validata è la release **prebuilt Vulkan** di llama.cpp (usa la GPU NVIDIA col solo driver, senza CUDA toolkit). Come installarlo: sezione [«Installare llama-server»](#installare-llama-server-per-il-colloquio) sotto (dettaglio in [`STATO_TECNICO.md`](STATO_TECNICO.md) §11).
- Spazio su disco per i modelli scaricati (LLM ~4.7 GB, voci Piper ~250 MB, STT scaricato al primo uso). I modelli vivono in `models/` e **non** sono versionati.

> Il **portale operatore** e gran parte del sistema funzionano anche **senza** LLM/GPU. L'LLM serve al colloquio del kiosk.

---

## Installazione

```bash
# 1. Clona e configura l'ambiente
git clone <URL-del-repo> progetto_bussola
cd progetto_bussola
cp .env.example .env            # password di sviluppo predefinite; cambiarle per qualsiasi uso reale

# 2. Backend (da backend/) — uv scarica Python 3.12, crea .venv e installa le
#    versioni bloccate in uv.lock (dev = test/lint/type-check; voice = faster-whisper + Piper)
cd backend
uv sync --all-extras
# Modello NER inglese (MIT) — non è una dipendenza del pyproject, si installa a parte
# nel venv uv (l'italiano usa i pattern + tokenizer blank):
uv pip install "en_core_web_lg @ https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl"
cd ..

# 3. Frontend (le due app React) — `npm ci` installa ESATTAMENTE dal package-lock.json
#    committato (riproducibile, non riscrive il lock). Usa `npm install` solo quando
#    vuoi aggiungere/aggiornare una dipendenza.
( cd frontend && npm ci )
( cd operator-portal && npm ci )
# Token di dispositivo del kiosk: frontend/.env deve avere VITE_KIOSK_TOKEN uguale a
# BUSSOLA_KIOSK_TOKEN nel root .env (altrimenti «postazione non autorizzata»). In dev i
# default combaciano già; run-stack.sh crea frontend/.env se manca. Sulla postazione
# blindata metti un token reale (in .env, mai committato).
cp frontend/.env.example frontend/.env

# 4. Voci Piper (it/en/fr/es) — per la lettura ad alta voce (TTS)
bash scripts/fetch-voice-models.sh

# 5. LLM per il colloquio: PRIMA installa llama-server (vedi «Installare llama-server» sotto),
#    poi questo scarica il modello (~4.7 GB, una tantum) e avvia il server su :8080.
bash scripts/serve-llm.sh
```

### Installare llama-server (per il colloquio)

`scripts/serve-llm.sh` richiede il binario **`llama-server`** ([llama.cpp](https://github.com/ggml-org/llama.cpp), MIT) sul `PATH` — l'errore `llama-server not found on PATH` significa che manca questo passo. Due vie (vedi anche [`STATO_TECNICO.md`](STATO_TECNICO.md) §11):

**Vulkan — consigliato e validato** (usa la GPU NVIDIA col solo driver, **nessun CUDA toolkit, nessuna build**):

1. Dalle [release di llama.cpp](https://github.com/ggml-org/llama.cpp/releases) scarica il prebuilt per Ubuntu: l'asset `llama-<tag>-bin-ubuntu-vulkan-x64.zip` (build validata nel pilota: **b10092**).
2. Scompattalo (es. in `~/llama-vulkan/llama-b10092/`) e metti quella cartella sul `PATH`:
   ```bash
   export PATH="$HOME/llama-vulkan/llama-b10092:$PATH"   # in ~/.bashrc per renderlo permanente
   ```
Requisiti runtime: loader Vulkan (`libvulkan1`) + driver NVIDIA (fornisce l'ICD).

**CUDA — alternativa** (build da sorgente, potenzialmente più veloce; richiede CUDA toolkit/`nvcc`; per Linux non esiste un prebuilt CUDA):

```bash
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
cmake -B build -DGGML_CUDA=ON && cmake --build build -j
export PATH="$PWD/build/bin:$PATH"
```

**Verifica**, poi torna al passo 5:

```bash
llama-server --version   # deve stampare la versione → ora `bash scripts/serve-llm.sh` funziona
```

> **Licenze (§3):** lo stack è open source e in prevalenza a licenza permissiva. Il modello NER italiano `it_core_news_lg` è CC BY-NC-SA e **non** va installato. Il motore TTS Piper è GPL-3.0 (eccezione documentata e approvata, valida perché il pilota è on-premise non distribuito). Dettagli in [`CREDITS.md`](CREDITS.md) e [`CLAUDE.md`](CLAUDE.md) §3.

---

## Avvio

### Un solo comando (consigliato)

```bash
scripts/run-stack.sh              # DB → migrazioni → bootstrap admin → API + kiosk + portale
scripts/run-stack.sh --with-llm   # come sopra, avviando anche llama-server (:8080)
scripts/run-stack.sh stop         # ferma tutto ciò che lo script ha avviato (+ DB)
```

Lo script fa il preflight delle porte, avvia PostgreSQL (Docker), applica le migrazioni, crea l'amministratore iniziale (idempotente) e attende che il backend risponda su `/health` prima di dichiararsi pronto. A fine avvio stampa gli URL:

- **Kiosk (persona):** <http://localhost:5173>
- **Portale operatore:** <http://localhost:5174>
- **API backend:** <http://127.0.0.1:8000>

Il primo accesso al portale usa l'amministratore di bootstrap (`admin` / `admin_dev_change_me` di default, da cambiare al primo login e configurabili via `BUSSOLA_ADMIN_USERNAME`/`BUSSOLA_ADMIN_PASSWORD`).

> **Solo sviluppo/localhost.** `run-stack.sh` usa le password di sviluppo di `.env` e lega tutto a `127.0.0.1`. Per la produzione vedi [`STATO_TECNICO.md`](STATO_TECNICO.md) §12.

### Componenti singoli (avvio manuale)

Da `backend/`, nel venv creato da uv (`source .venv/bin/activate`, oppure anteponi `uv run` a ogni comando) e con il DB su (`docker compose up -d db`):

```bash
python -m bussola.data.migrate                                              # applica le migrazioni
BUSSOLA_ADMIN_USERNAME=admin BUSSOLA_ADMIN_PASSWORD=… python -m bussola.auth.bootstrap   # primo admin
uvicorn bussola.api.app:create_app --factory --host 127.0.0.1 --port 8000   # API
```

Kiosk e portale: `npm run dev` rispettivamente da `frontend/` (`:5173`) e `operator-portal/` (`:5174`).

### Verifica «PC nuovo funziona»

```bash
scripts/smoke-full-stack.sh   # avvia lo stack, sonda health + i due frontend + login reale, poi ferma tutto
```

---

## Test e qualità

**Backend** (da `backend/`, nel venv uv — `source .venv/bin/activate` o `uv run …`; alcuni test richiedono `docker compose up -d db`):

```bash
pytest -q          # test (guardrail e sicurezza per primi)
ruff check .       # lint
mypy src           # type-check (strict)
```

**Frontend** (da `frontend/` e da `operator-portal/`):

```bash
npm test && npm run typecheck && npm run lint && npm run build
```

Il progetto è sviluppato in **TDD** con **soli dati sintetici** (mai dati reali di persone). I test più importanti sono quelli sulla tenuta del sistema: controllo dell'ambito, resistenza alla manipolazione, nessuna fuoriuscita di dati personali ([`CLAUDE.md`](CLAUDE.md) §9).

---

## Struttura del repository

```
backend/          API + colloquio + estrazione + guardrail + matching + audit (Python)
frontend/         Kiosk della persona detenuta (React)
operator-portal/  Portale dell'operatore (React)
scripts/          run-stack.sh, fetch-voice-models.sh, serve-llm.sh, smoke-full-stack.sh
db-init/          Script di inizializzazione PostgreSQL (ruoli, schemi)
models/           Modelli scaricati (LLM, voci) — NON versionato
docs/             Specifiche e piani di implementazione
CLAUDE.md         Documento-nucleo: cosa costruiamo e perché (missione, principi, linee rosse)
STATO_TECNICO.md  Documento tecnico vivo: come (stack, modelli, comandi, decisioni)
CREDITS.md        Licenze e attribuzioni dei componenti e dei modelli
```

---

## Licenza e uso

Progetto pilota a scopo di reinserimento. Stack interamente open source (vedi [`CREDITS.md`](CREDITS.md)). I dati trattati sono **solo lavorativi**, pseudonimizzati e segregati; nessun dato esce dal sistema senza un flusso di autorizzazione esplicito.
