# Switch del backend a uv — design

**Data:** 2026-07-30 · **Ambito:** tooling di build/dipendenze del backend · **Fase:** 1 (trasversale, dev-experience)

## Obiettivo

Rendere la **replica su un PC nuovo** semplice e riproducibile, eliminando due attriti emersi in pratica:

1. su un PC con **Python 3.14** l'installazione con pip fallisce (le dipendenze compilate — `psycopg[binary]`, `ctranslate2`/faster-whisper, `onnxruntime`/piper-tts, `spacy`/presidio, `pydantic-core` — spesso non hanno wheel per una versione appena uscita → build da sorgente che fallisce);
2. senza lockfile, le versioni installate possono divergere tra macchine.

**Decisione:** adottare **uv** come unico strumento per Python e dipendenze del backend (**uv-only**). uv fissa Python **3.12** su qualsiasi macchina e installa versioni esatte da un **`uv.lock` committato**.

Questo **rovescia deliberatamente la PR #30** (che aveva messo `backend/uv.lock` in `.gitignore` assumendo pip+venv), esattamente come la nota di #30 prevedeva: «If uv is ever adopted deliberately, remove this line and commit the lock».

## Perché uv

- **Gestione della versione di Python:** con `backend/.python-version` = `3.12`, `uv sync` scarica/usa automaticamente una 3.12.x recente, indipendentemente dal Python di sistema (risolve il 3.14).
- **Riproducibilità:** `uv sync --all-extras` installa le versioni **esatte** bloccate in `uv.lock`.
- **Vincoli (§3):** uv è open-source (Apache-2.0/MIT), gira in locale, a costo zero. Legge il `pyproject.toml` esistente → nessuna ristrutturazione.
- **Governance:** è una scelta di tooling (documento `STATO_TECNICO`), **non** una modifica al nucleo `CLAUDE.md` (missione/ruoli/linee rosse invariati).

## Flusso di setup (nuovo, backend)

Prerequisito: **uv** installato (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
cd backend
uv sync --all-extras   # fetch Python 3.12 → crea .venv → installa deps bloccate (dev + voice)
# Modello NER inglese (MIT). NB: il venv uv non ha pip → si usa `uv pip install` del wheel,
# non `spacy download` (che richiederebbe pip nel venv). L'italiano usa pattern + tokenizer blank.
uv pip install "en_core_web_lg @ https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl"
```

- **Python non è più un prerequisito manuale** (lo fornisce uv). Restano prerequisiti Docker e Node.
- **Gate di qualità:** invariato nei comandi. Si eseguono nel venv creato da uv (`source backend/.venv/bin/activate`, come già fa `run-stack.sh`, oppure `uv run pytest -q` / `uv run ruff check .` / `uv run mypy src`).
- **Frontend, voci Piper, LLM:** invariati (`npm install`, `scripts/fetch-voice-models.sh`, `scripts/serve-llm.sh`).

## File toccati

| File | Modifica |
|---|---|
| `backend/.python-version` | **nuovo** — contenuto `3.12` |
| `backend/uv.lock` | **rigenerato fresco e committato** (`uv lock` su questa macchina, che ha 3.12) |
| `.gitignore` | rimossa la riga che ignora `backend/uv.lock` (le altre restano) |
| `README.md` | sezione prerequisiti + installazione backend riscritta a **uv** (istruzioni pip rimosse) |
| `STATO_TECNICO.md` | §11 setup backend → uv; nuova riga di decisione §15 (rovescia #30, motivazione) |
| `scripts/run-stack.sh` | **solo** il messaggio del preflight «`backend/.venv` mancante» ora rimanda a `uv sync` (nessun cambio di comportamento) |

`backend/pyproject.toml` — **le dipendenze non cambiano** (uv usa il `build-system` setuptools e le `optional-dependencies` `dev`/`voice` già dichiarate; `requires-python` resta `>=3.12`, il pin operativo a 3.12 lo dà `.python-version`). **Unica aggiunta di config** (emersa in verifica): `[tool.ruff.lint] select = ["E4","E7","E9","F"]` — uv installa l'ultimo ruff (0.16) e, senza un `select` esplicito, il suo default per una config nuda si è allargato rispetto alla ruff con cui il progetto era verde, segnalando 114 pattern voluti (FastAPI `Depends`, `except` delle reti di degrado). Fissare il set esplicitamente **preserva il contratto di lint storico** e rende il gate deterministico rispetto alla versione di ruff.

## Fuori scope

- Nessun cambio alle **dipendenze** di `pyproject.toml` (versioni, build-backend); l'unica modifica è la config lint di ruff (sopra).
- `run-stack.sh` non diventa un installer (resta un «runner»; niente `uv sync` automatico).
- Frontend e script modelli invariati.

## Verifica (prima della PR)

- uv installato in locale; `uv lock` rigenera `backend/uv.lock`.
- `uv sync --all-extras` in un **`.venv` pulito** (rimosso e ricreato) → installazione ok con Python 3.12.
- **Gate backend verde**: `pytest -q && ruff check . && mypy src` (con `docker compose up -d db`).
- `run-stack.sh` continua a trovare/attivare `backend/.venv` e ad avviare lo stack.
- `git check-ignore backend/uv.lock` non lo ignora più; `uv.lock` risulta tracciato.

## Criteri di completamento

- Setup «PC nuovo» documentato **solo** con uv; `.python-version` presente; `uv.lock` committato e non ignorato.
- Gate backend verde dopo `uv sync --all-extras` in venv pulito.
- `README.md` e `STATO_TECNICO.md` §11 coerenti (nessun residuo di istruzioni pip); riga di decisione §15 registra il rovesciamento di #30.
