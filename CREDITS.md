# CREDITS — Attribuzioni dei componenti di terze parti

**Progetto «Bussola»** · Assistente per la profilazione lavorativa delle persone detenute

Questo file elenca i modelli, i motori e le librerie di terze parti usati da Bussola,
con **autore, licenza e link**, in conformità con `CLAUDE.md` §3 (stack open source) e
§11 (documenti di progetto in italiano). Le voci e i modelli non vivono nel repository
(sono scaricati on-premise); qui sono comunque attribuiti perché fanno parte dello stack
distribuito con il sistema.

Salvo l'unica eccezione indicata (motore TTS Piper), tutti i componenti hanno licenza
**permissiva**. Dove una licenza **richiede l'attribuzione** (CC-BY) o è **copyleft**
(GPL/LGPL), è segnalato esplicitamente.

---

## ⚠️ Attribuzioni obbligatorie (da mostrare prima del pilota)

Le licenze seguenti **impongono** un credito visibile. Vanno riportate nella
documentazione di deployment e/o in una schermata «crediti/informazioni» del kiosk.

- **Voce vocale francese** — *SIWIS French Speech Synthesis Database*
  - Autore: **The Centre for Speech Technology Research (CSTR), University of Edinburgh**
  - Licenza: **Creative Commons Attribution 4.0 (CC-BY-4.0)** — <https://creativecommons.org/licenses/by/4.0/>
  - Fonte: <https://datashare.is.ed.ac.uk/handle/10283/2353>
  - **Modifiche:** la voce Piper `fr_FR-siwis-medium` è un modello **derivato** dal database SIWIS (fine-tuning + ri-encoding tramite Piper). CC-BY-4.0 richiede di indicare che il materiale è stato modificato: questa nota lo assolve.

---

## Modelli

| Componente | Uso | Autore | Licenza |
|---|---|---|---|
| **Qwen2.5-7B-Instruct** (GGUF Q4_K_M) · fallback **Qwen2.5-1.5B / 0.5B-Instruct** | LLM (dialogo, estrazione, guardrail) | Alibaba Cloud / Qwen Team | **Apache-2.0** |
| **Whisper** `large-v3-turbo` (via CTranslate2) | STT (riconoscimento vocale) | OpenAI | **MIT** |
| **spaCy** `en_core_web_lg` | modello NER per il filtro PII (Presidio) | Explosion | **MIT** |

### Voci TTS (Piper, formato ONNX)

| Voce | Lingua | Dataset / Autore | Licenza |
|---|---|---|---|
| `it_IT-paola-medium` | Italiano | `paolapersico1/Voice-Dataset-Italian` | **CC0-1.0** (public domain) |
| `en_US-ljspeech-medium` | Inglese | LJ Speech Dataset (Keith Ito) | **Public domain** |
| `fr_FR-siwis-medium` | Francese | SIWIS DB — CSTR, Univ. Edinburgh | **CC-BY-4.0** (vedi sopra) |
| `es_ES-davefx-medium` | Spagnolo | `davefx` (OHF-Voice) | **CC0** (public domain) |

> Nota tecnica (§14): le voci it/es/fr sono *finetuned* dalla base inglese `lessac`
> (dataset Blizzard 2013, research-only). I loro **dataset** sono permissivi; il rischio
> residuo di derivazione dei pesi è stato **accettato e documentato** (pilota non
> commerciale, on-premise). L'inglese `ljspeech` è addestrato da zero (nessuna derivazione).

## Motori e serving

| Componente | Uso | Autore | Licenza |
|---|---|---|---|
| **llama.cpp** (`llama-server`) | serving dell'LLM | Georgi Gerganov & contributori | **MIT** |
| **faster-whisper** (+ **CTranslate2**) | runtime STT | SYSTRAN | **MIT** |
| **onnxruntime** | runtime delle voci ONNX | Microsoft | **MIT** |
| **Piper** (`piper-tts` 1.x, OHF-Voice) | motore TTS | OHF-Voice & contributori | **GPL-3.0-or-later** ⚠️ (eccezione §3, vedi sotto) |

## Librerie backend (Python, runtime)

| Libreria | Autore | Licenza |
|---|---|---|
| **FastAPI** | Sebastián Ramírez | MIT |
| **Uvicorn** | Encode | BSD-3-Clause |
| **Pydantic** | Pydantic | MIT |
| **httpx** | Encode | BSD-3-Clause |
| **psycopg** (v3) | Daniele Varrazzo & contributori | **LGPL-3.0-only** (copyleft-lite, ammesso da §3) |
| **argon2-cffi** | Hynek Schlawack | MIT |
| **python-multipart** | Andrew Dunham | Apache-2.0 |
| **Presidio** (analyzer + anonymizer) | Microsoft | MIT |
| **spaCy** | Explosion | MIT |

## Librerie frontend (JavaScript/TypeScript, runtime — kiosk e portale)

| Libreria | Autore | Licenza |
|---|---|---|
| **React** / **React-DOM** | Meta | MIT |
| **i18next** / **react-i18next** | i18next | MIT |
| **react-router-dom** (solo portale operatore) | Remix | MIT |

## Infrastruttura

| Componente | Autore | Licenza |
|---|---|---|
| **PostgreSQL** | PostgreSQL Global Development Group | PostgreSQL License (permissiva, tipo BSD) |
| **Docker / docker compose** | Docker, Inc. | Apache-2.0 |
| **Chromium** (`--kiosk`) | The Chromium Authors | BSD-3-Clause (+ licenze di terze parti) |

## Solo sviluppo / build (NON distribuito nel runtime)

Vite, TypeScript, ESLint, typescript-eslint, Vitest, @testing-library, jsdom, pytest,
Ruff, mypy — tutte **MIT/BSD/Apache**. Nota (§14): tra le dipendenze **transitive di
solo sviluppo** compaiono `caniuse-lite` (**CC-BY-4.0**, dati) e `argparse`
(**Python-2.0**); sono usate solo a build-time e **non finiscono nel bundle** distribuito.

---

## Eccezione a `CLAUDE.md` §3 (licenza permissiva) — motore TTS Piper

Il motore **Piper** (`piper-tts` 1.x, riscrittura `OHF-Voice/piper1-gpl`) è
**GPL-3.0-or-later** (copyleft), non permissivo: la fonemizzazione lega **espeak-ng**,
a sua volta GPL. Il vecchio `rhasspy/piper` (0.x) era MIT, da cui l'assunzione iniziale
poi corretta.

Questa è l'**unica eccezione** alla clausola «permissiva» di §3, **approvata dalla
Direzione (2026-07-28)** con la procedura di governance §0. È ammessa perché:

- GPL resta **open source, gratuito e locale** → i vincoli §3 «open source», «budget
  nullo» e «locale/on-premise» restano pienamente soddisfatti;
- il pilota gira **on-premise, senza distribuzione a terzi**: gli obblighi copyleft della
  GPL si attivano sulla **distribuzione**, che qui non avviene.

**Da rivalutare** se Bussola venisse distribuito all'esterno o usato commercialmente:
in tal caso isolare Piper come **processo separato** (arm's-length, consentito dalla GPL)
oppure sostituire il motore TTS con uno permissivo. Dettaglio in `STATO_TECNICO.md`
(§4.3, §14 e registro decisioni).
