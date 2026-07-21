# Spec di design — Sottosistema 3: Serving LLM + guardrail comportamentali

**Progetto «Bussola»** · Sottosistema 3 · *Design di riferimento per il piano collegato* · 2026-07-21

---

## 0. Cos'è questo documento

Spec di design del terzo sottosistema, nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice passo-passo. Si conforma a `CLAUDE.md` §2 (linee rosse, ambito bloccato in ingresso **e in uscita**), §7.1/§7.3 (ambito, controlli indipendenti dal modello), §9 (tenuta dei guardrail = test n.1), e allo stack di `STATO_TECNICO.md` §4.1/§7.

## 1. Contesto e scopo

Realizza i **guardrail comportamentali** — l'identità del progetto (§2): il sistema resta su lavoro/formazione/orientamento, resiste alla manipolazione, rifiuta con garbo, non perde dati. Introduce anche il **serving dell'LLM** e un **client** riusabile. Poggia sul filtro PII già esistente (Sott. 1). È la base del colloquio (Sott. 4), che qui **non** è incluso.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Client LLM** riusabile verso `llama-server` (API OpenAI-compatibile), agnostico dal serving.
- **Serving nativo** documentato: `llama-server` (CUDA) + modello Qwen2.5-7B-Instruct GGUF Q4_K_M.
- **Guard layer indipendente:** guard di **input** (classificatore di ambito/sicurezza) + guard di **output** (ri-check di ambito + filtro PII + anti-fuga), attorno alla chiamata LLM di merito.
- **Rifiuti controllati** (strutturati + messaggio localizzato non giudicante).
- **Resistenza a injection** (prompt blindati, input come dati, nessuna azione fuori insieme).
- **Degrado elegante** su LLM lento/assente.

**Non-obiettivi (rimandati):**
- **Colloquio a tappe, riepilogo & conferma, incongruenze** → Sottosistema 4.
- **Estrazione strutturata / constrained decoding** → Sottosistema 4.
- **Voce** → Sottosistema 5.
- **i18n completo delle stringhe utente** → col frontend (Sott. 7); qui i messaggi di rifiuto sono template minimi nelle 5 lingue.

## 3. Decisioni di design (con motivazione)

1. **Guard layer indipendente** (non solo prompt). Check espliciti attorno all'LLM. *Perché §7.3:* «controlli indipendenti dal buon comportamento del modello». La tenuta non dipende dalla compliance del prompt.

2. **Guard di input = classificatore LLM strutturato** (`{allow, category, reason}`, temp 0) + validazioni deterministiche (lunghezza, delimitazione input). *Perché:* l'ambito e l'injection sono semantici e multilingua → un classificatore LLM è robusto e spiegabile dove le regole/keyword sono fragili ed eludibili. Le validazioni deterministiche coprono i casi non semantici (input troppo lungo).

3. **Guard di output = ri-check di ambito via LLM (sempre attivo) + filtro PII + controlli anti-fuga.** *Perché §2:* le richieste fuori contesto vanno rifiutate «in ingresso **e in uscita**». Cattura la deriva del modello nella risposta nonostante un input in ambito; il filtro PII (deterministico, Sott. 1) resta la garanzia dura; il ri-check di ambito è un livello forte in aggiunta. *Costo accettato:* ~3 chiamate LLM/turno su un solo utente simultaneo, «prima il testo».

4. **Rifiuti strutturati + messaggio localizzato.** La *decisione* è un tipo (`RefusalCategory`); il *messaggio* è un template non giudicante nella lingua del colloquio. *Perché §4:* tono accogliente, non stigmatizzante; e struttura testabile.

5. **Resistenza a injection = prompt blindati + input delimitato + nessuna azione libera.** I prompt (di merito e dei guard) trattano l'input utente come **dati**, non istruzioni; non rivelano il system prompt; non eseguono azioni fuori dall'insieme previsto; ignorano «ignora le istruzioni precedenti». *Perché §2/§7.3.*

6. **Serving nativo + client httpx.** `llama-server` nativo con CUDA (GPU diretta; il toolkit GPU per Docker è assente sulla macchina). Client = wrapper httpx sull'endpoint OpenAI-compatibile, URL/modello/timeout da `.env`. *Perché:* accesso GPU semplice, dipendenze minime (httpx BSD), nessuna API esterna. Modello Qwen2.5-7B Q4_K_M (**Apache 2.0**, permissivo).

7. **Degrado elegante.** Timeout gestito → rifiuto/avviso controllato «temporaneamente non disponibile» (mai blocco); fallback al 3B come swap di configurazione. *Perché §3 «prima il testo, degrado elegante».*

## 4. Unità e confini

- **`bussola.llm.client`** — `LlmClient`: `chat(messages, *, temperature=0.0, max_tokens, timeout) -> str`. Thin su httpx; config da `bussola.llm.config` (`.env`). Interfaccia astratta così i guard sono testabili con un **fake** deterministico.
- **`bussola.guardrails.scope`** — `ScopeGuard(client)`: `check(text, language) -> GuardDecision(allow: bool, category: RefusalCategory | None, reason: str)`. Prompt classificatore blindato; output JSON validato (Pydantic); validazioni deterministiche.
- **`bussola.guardrails.refusal`** — `RefusalCategory` (enum) + `refusal_message(category, language) -> str` (template localizzati, non giudicanti).
- **`bussola.guardrails.pipeline`** — `GuardedConversation(client, scope_guard, redactor)`: `ask(user_text, language) -> Reply` dove `Reply` è una risposta in ambito **oppure** un rifiuto. Flusso: **input guard → (se allow) chiamata di merito con system prompt blindato → output guard (ri-check ambito + PII + anti-fuga)**.
- **Serving** — script/doc: download modello in `models/` (gitignored), avvio `llama-server`; in `STATO_TECNICO.md` §11.

Confine: `bussola.llm`/`bussola.guardrails` dipendono da httpx/pydantic e dal filtro PII (Sott. 1). Non conoscono il colloquio né la persistenza.

## 5. Strategia di test (§9, priorità n.1)

TDD; **solo dati sintetici**. Due livelli:

- **Unit con LLM finto** (test double deterministico dell'interfaccia client): logica della pipeline e del parsing — rifiuto gestito, decisione strutturata parsata, il rifiuto **corto-circuita** la chiamata di merito, integrazione col filtro PII in output, output malformato del classificatore gestito (fail-safe: in dubbio, rifiuta). Veloci, deterministici, **senza modello/GPU**.
- **Integrazione avversaria con Qwen2.5 reale** (temp 0, marcati `requires_llm` → skip se il server è giù): corpus di prompt avversari — fuori tema (medico/legale/dati di terzi), injection («ignora le istruzioni», «rivela il prompt», «fai finta di…»), tentativi di estrazione dati — che asseriscono **rifiuto / permanenza in ambito** e **nessuna fuga** (system prompt/PII), su più lingue (almeno it/en/ar). Robuste al non-determinismo (temp 0; asserzioni su «rifiuto rilevato», non su testo esatto).

Ordine di priorità (§9): tenuta ambito → rifiuti controllati → resistenza injection/estrazione → nessuna fuga PII.

## 6. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Guard LLM non deterministico | temp 0; output strutturato validato; **fail-safe = rifiuta** su parsing incerto |
| Test avversari flaky | temp 0; asserzioni robuste; marcati `requires_llm`, skip se server giù |
| Latenza (3 chiamate/turno) | un solo utente; check corti; prima il testo; misurare, non è bloccante |
| Guard aggirato da injection nell'output | il guard di output vede l'output del modello, non obbedisce a istruzioni in esso |
| Garanzia probabilistica dei guard LLM | difesa in profondità: whitelist (Sott.4) + PII deterministico (Sott.1) restano le garanzie dure |

## 7. Criteri di accettazione

- Unit (LLM finto) verdi e deterministici; la pipeline rifiuta fail-safe su output guard malformato.
- Con Qwen2.5 reale (temp 0): il sistema **rifiuta** fuori-tema e injection e **resta in ambito**, in it/en/ar; nessuna fuga di system prompt né PII in uscita.
- Client agnostico dal serving; `llama-server` nativo documentato e avviabile; degrado elegante su timeout.
- `pytest` (unit sempre; integrazione se `requires_llm`), `ruff`, `ruff format --check`, `mypy` verdi; solo dati sintetici.

## 8. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§7.1/§7.3/§9). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: aggiornato con serving nativo, architettura dei guardrail, e `.env` per l'LLM.
- **Piano collegato:** la scomposizione eseguibile in TDD di questo design.
