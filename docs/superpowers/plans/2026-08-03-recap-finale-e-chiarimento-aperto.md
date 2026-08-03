# Recap finale + chiarimento aperto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere al colloquio (a) un chiarimento aperto per-sezione quando l'estrazione è ambigua/incoerente, e (b) un recap finale schematico del profilo che la persona verifica e corregge a voce.

**Architecture:** Tre reti (chiarimento per-sezione → incongruenza finale esistente → recap). Il recap è la resa del profilo GIÀ salvato (nessun LLM per generarlo); l'LLM serve solo per il chiarimento per-sezione e per instradare la correzione del recap alla sezione giusta. Backend nel flusso `Interview`; kiosk con un nuovo schermo `Recap`.

**Tech Stack:** Backend Python 3.12 (pytest, doppie LLM deterministiche in `tests/interview/conftest.py`); kiosk React/TS/Vite (vitest, i18n react-i18next, 5 lingue it/en/fr/es/ar).

## Global Constraints

- **Nessuna modifica al nucleo** (§0): questo realizza §5/§7.1 già esistenti. Non toccare `CLAUDE.md`.
- **§4:** testo semplice, niente emoji, degrado elegante; max UNA domanda di chiarimento aperta per sezione.
- **Lingua:** ogni testo generato è nella lingua scelta (regola come in `summarize`/`find_incongruence`, via `bussola.languages.language_name`); nuove stringhe kiosk in tutte e 5 le lingue (it/en/fr/es/ar).
- **§3 degrado:** un fallimento del chiarimento per-sezione NON blocca il turno (fail-open → si va al riepilogo); un fallimento della correzione del recap NON completa e NON perde dati (si resta sul recap con messaggio).
- **§7.3:** il recap non introduce nuove chiamate LLM in generazione; i dati sono già filtrati PII a ogni `save`.
- **TDD:** doppie LLM deterministiche (`make_fake_json_llm` con `json_responses`/`text_responses`/`output_responses`); il canale outbound auto-ALLOW già esiste. Test live esistenti restano lo standard finale (§10) ma NON sono richiesti in questo piano.
- **Stile:** `ruff check`, `ruff format --check`, `mypy src` verdi; kiosk `typecheck`/`lint`/`build`/`vitest` verdi.

## File Structure

- Create `backend/src/bussola/interview/clarify.py` — `find_section_clarification` (+ `apply_recap_correction`).
- Modify `backend/src/bussola/interview/interview.py` — stati `_awaiting_section_clarification`/`_awaiting_recap`; wiring del chiarimento; produzione recap; confirm/correct del recap. `Step` guadagna `recap`.
- Modify `backend/src/bussola/api/kiosk/routers/interview.py` — `StepOut` guadagna `recap: WorkProfile | None`; le 3 costruzioni di `StepOut` passano `recap=step.recap`.
- Modify `frontend/src/types.ts` — `StepKind` guadagna `'recap'`; `Step` guadagna `recap?: WorkProfileView`.
- Modify `frontend/src/state/kioskMachine.ts` — nessun cambio logico (mappa già `step.kind`→screen); verificare che `recap` sia gestito.
- Modify `frontend/src/App.tsx` — `case 'recap'`.
- Create `frontend/src/screens/Recap.tsx` — resa lista + Sì/Correggi + voce.
- Modify `frontend/src/i18n/locales/{it,en,fr,es,ar}.ts` — blocco `recap` (intestazioni sezioni + etichette enum).

Backend tests: `backend/tests/interview/test_clarify.py` (nuovo), `backend/tests/interview/test_interview.py` (esteso), `backend/tests/api/kiosk/test_interview_endpoints.py` (esteso). Kiosk tests: `frontend/src/screens/Recap.test.tsx` (nuovo), `frontend/src/state/kioskMachine.test.ts` (esteso), `frontend/src/a11y.audit.test.tsx` (esteso).

---

### Task 1: `find_section_clarification` (chiarimento per-sezione)

**Files:**
- Create: `backend/src/bussola/interview/clarify.py`
- Test: `backend/tests/interview/test_clarify.py`

**Interfaces:**
- Consumes: `LlmClient` (`chat_json(messages, *, json_schema)`), `Section` (`bussola.interview.sections`), `WorkProfile`, `bussola.languages.language_name`.
- Produces: `find_section_clarification(client: LlmClient, section: Section, extracted: BaseModel, profile: WorkProfile, language: str) -> str | None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/interview/test_clarify.py
from bussola.interview.clarify import find_section_clarification
from bussola.interview.sections import SECTIONS
from bussola.interview.extraction import extract_section  # noqa: F401 (context)
from bussola.profile.models import WorkProfile


class _Json:
    def __init__(self, responses): self._r = list(responses); self.calls = []
    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
        self.calls.append(messages)
        return self._r.pop(0)
    def chat(self, *a, **k): raise AssertionError("no text call")


EXPERIENCES = SECTIONS[1]  # key == "experiences"


def test_returns_question_when_ambiguous():
    client = _Json([{"needs_clarification": True, "question": "Che lavoro facevi di preciso?"}])
    q = find_section_clarification(client, EXPERIENCES, EXPERIENCES.extraction_model(), WorkProfile(pseudonym_id="P-1"), "it")
    assert q == "Che lavoro facevi di preciso?"


def test_returns_none_when_clear():
    client = _Json([{"needs_clarification": False, "question": ""}])
    assert find_section_clarification(client, EXPERIENCES, EXPERIENCES.extraction_model(), WorkProfile(pseudonym_id="P-1"), "it") is None


def test_fail_open_on_llm_error():
    class Boom:
        def chat_json(self, *a, **k): raise RuntimeError("down")
    assert find_section_clarification(Boom(), EXPERIENCES, EXPERIENCES.extraction_model(), WorkProfile(pseudonym_id="P-1"), "it") is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/interview/test_clarify.py -q`
Expected: FAIL (module `clarify` not found).

- [ ] **Step 3: Implement**

```python
# backend/src/bussola/interview/clarify.py
"""Per-section clarity check + recap-correction routing (§5/§7.1)."""

from __future__ import annotations

from pydantic import BaseModel

from bussola.interview.sections import SECTIONS, Section
from bussola.languages import language_name
from bussola.llm.client import LlmClient
from bussola.profile.models import WorkProfile

_CLARIFY_SCHEMA = {
    "type": "object",
    "properties": {"needs_clarification": {"type": "boolean"}, "question": {"type": "string"}},
    "required": ["needs_clarification", "question"],
    "additionalProperties": False,
}


def find_section_clarification(
    client: LlmClient, section: Section, extracted: BaseModel, profile: WorkProfile, language: str
) -> str | None:
    """A gentle OPEN question if this section's extraction is ambiguous or
    incoherent with the profile so far, else None. Fail-open: None on any error
    (§3 — a clarity check must never block the turn)."""
    name = language_name(language)
    prompt = (
        "You review one section just extracted from a person's work interview. "
        "Ask a clarification ONLY IF a key field is ambiguous or clearly incoherent "
        "with what the person already said — for example a role that is a generic "
        "verb ('lavorato', 'fatto') instead of a job, a duration that cannot be "
        "right, or an experience that contradicts an earlier section. A MISSING or "
        "EMPTY field is NEVER a reason to ask (the profile is intentionally minimal). "
        "When in doubt, do NOT ask. If (and only if) needed, write ONE short, gentle, "
        f"non-judgmental OPEN question ENTIRELY in {name} (code '{language}') — every "
        "word in that language, simple everyday words, and NO emoji or symbols (it is "
        'read aloud). Reply JSON {"needs_clarification": bool, "question": string}; '
        "use false + empty question when no clarification is needed."
    )
    user = (
        f"[section]\n{section.key}\n[extracted]\n{extracted.model_dump_json()}\n"
        f"[profile so far]\n{profile.model_dump_json()}"
    )
    try:
        raw = client.chat_json(
            [{"role": "system", "content": prompt}, {"role": "user", "content": user}],
            json_schema=_CLARIFY_SCHEMA,
        )
    except Exception:
        return None
    if raw.get("needs_clarification") is True and isinstance(raw.get("question"), str):
        return raw["question"] or None
    return None
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/interview/test_clarify.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/bussola/interview/clarify.py backend/tests/interview/test_clarify.py
git commit -m "feat(interview): find_section_clarification (chiarimento per-sezione, fail-open)"
```

---

### Task 2: Wire per-section clarification into the interview flow

**Files:**
- Modify: `backend/src/bussola/interview/interview.py`
- Test: `backend/tests/interview/test_interview.py`

**Interfaces:**
- Consumes: `find_section_clarification` (Task 1); existing `_present`, `_summarize_section`, `_section_answer`, guard, `extract_section`.
- Produces: new instance state `_awaiting_section_clarification: bool`, `_section_clarification: str | None`; behavior: after extracting a section, if a clarification is returned, emit a `clarification` Step and, on the reply, append+re-extract then go to the summary.

- [ ] **Step 1: Write the failing tests** (append to `test_interview.py`; uses the existing `make_fake_json_llm`, `ScopeGuard`, `FakeRepo`, `ALLOW`, `_FakeRedactor`)

```python
def test_ambiguous_section_asks_one_open_clarification_then_summarizes(make_fake_json_llm):
    # answer -> guard ALLOW(text) + extract(json) + clarity NEEDS(json) -> clarification step;
    # reply -> guard ALLOW(text) + re-extract(json) + clarity SKIPPED (only once) -> summary(text)
    skills = {"skills": [], "languages": [], "digital_literacy": None}
    client = make_fake_json_llm(
        json_responses=[skills, {"needs_clarification": True, "question": "Che sai fare di preciso?"},
                        skills],
        text_responses=[ALLOW, ALLOW, "Ho capito. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it", redactor=_FakeRedactor())
    itw.start()
    s1 = itw.submit("boh, cose")
    assert s1.kind == "clarification" and "preciso" in s1.text
    s2 = itw.submit("so cucinare")
    assert s2.kind == "summary"  # one clarification only, then summary


def test_clear_section_skips_clarification(make_fake_json_llm):
    skills = {"skills": [{"name": "cucina", "kind": "technical", "evidence": "stated"}],
              "languages": [], "digital_literacy": None}
    client = make_fake_json_llm(
        json_responses=[skills, {"needs_clarification": False, "question": ""}],
        text_responses=[ALLOW, "Sai cucinare. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it", redactor=_FakeRedactor())
    itw.start()
    assert itw.submit("so cucinare").kind == "summary"
```

Note: `make_fake_json_llm` must serve `find_section_clarification`'s `chat_json` from the SAME `json_responses` queue in call order — order the json responses exactly as the comments show (extract, clarify, [re-extract]).

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/interview/test_interview.py -k clarification -q` → FAIL.

- [ ] **Step 3: Implement in `interview.py`**

Add import: `from bussola.interview.clarify import find_section_clarification`.

In `__init__`, add after `_last_summary`:
```python
        self._awaiting_section_clarification = False
        self._section_clarification: str | None = None
```

Reset both to their defaults in `start`, `start_on`, `start_followup` (alongside the existing resets: `self._awaiting_section_clarification = False`, `self._section_clarification = None`).

In `_summarize_section`, BEFORE building the summary, insert the clarity check (only when not already resolving a clarification):
```python
    def _summarize_section(self, session, section):
        extracted = extract_section(self._client, section, self._section_answer, self._language)
        if not self._awaiting_section_clarification:
            question = find_section_clarification(
                self._client, section, extracted, session.profile, self._language
            )
            if question is not None:
                shown = self._present(question)
                if shown is not None:  # off-scope generated text withheld (§9); else fall through
                    self._awaiting_section_clarification = True
                    self._section_clarification = question
                    return Step("clarification", shown)
        self._awaiting_section_clarification = False
        self._section_clarification = None
        summary_text = self._present(summarize(self._client, section, extracted, self._language))
        if summary_text is None:
            summary_text = _generic_confirmation(self._language)
        session.merge(extracted)
        self._awaiting_confirmation = True
        self._last_summary = summary_text
        return Step("summary", summary_text)
```

In `_submit`, add a branch BEFORE the `_awaiting_confirmation` branch, handling the reply to a section clarification (mirrors the correction-guard, judged against the clarification question):
```python
        if self._awaiting_section_clarification:
            section = session.current_section
            assert section is not None
            decision = self._guard.check(
                answer, self._language, question=self._section_clarification or base_question(section, self._language)
            )
            if not decision.allow:
                return Step("refusal", refusal_message(decision.category or RefusalCategory.OUT_OF_SCOPE, self._language))
            self._section_answer = f"{self._section_answer}\n{answer}".strip()
            return self._summarize_section(session, section)
```

(The `_awaiting_section_clarification` flag stays True through the guard, so `_summarize_section` skips a second clarity check and goes to the summary; it is cleared inside `_summarize_section`.)

- [ ] **Step 4: Run to verify pass + no regressions**

Run: `python -m pytest tests/interview/ -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/bussola/interview/interview.py backend/tests/interview/test_interview.py
git commit -m "feat(interview): apri un chiarimento per-sezione sull'ambiguità (max 1/sezione)"
```

---

### Task 3: Recap Step payload + emit recap at the end

**Files:**
- Modify: `backend/src/bussola/interview/interview.py` (`Step`, `_finalize`/`_complete`, `_awaiting_recap`)
- Modify: `backend/src/bussola/api/kiosk/routers/interview.py` (`StepOut.recap` + 3 constructions)
- Test: `backend/tests/interview/test_interview.py`, `backend/tests/api/kiosk/test_interview_endpoints.py`

**Interfaces:**
- Consumes: `WorkProfile`.
- Produces: `Step` dataclass gains `recap: WorkProfile | None = None`; the completed interview first emits `Step("recap", <intro>, recap=profile)` and sets `_awaiting_recap`. `StepOut` gains `recap: WorkProfile | None = None`.

- [ ] **Step 1: Write the failing tests**

```python
# test_interview.py — after all sections confirmed + incongruence None, a recap step carries the profile
def test_interview_ends_with_a_recap_carrying_the_profile(make_fake_json_llm):
    repo = FakeRepo()
    json_responses, text_responses = [], []
    _confirm_all_sections(json_responses, text_responses)  # each section: extract + clarity(false) + confirm
    json_responses.append({"has_incongruence": False, "clarification": ""})
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    last = None
    for _ in range(5):
        assert itw.submit("una risposta di lavoro").kind == "summary"
        last = itw.submit("sì, è corretto")
    assert last is not None and last.kind == "recap"
    assert last.recap is not None and last.recap.pseudonym_id  # carries the saved profile
```

`_confirm_all_sections` must be updated to add a `{"needs_clarification": False, "question": ""}` json response per section (right after each section's extraction), since Task 2 added a clarity check per section.

```python
# test_interview_endpoints.py — the /submit response serializes recap
def test_submit_recap_step_serializes_the_profile(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)

    class RecapInterview(Interview):
        def __init__(self) -> None:  # type: ignore[super-init-not-called]
            pass
        def submit(self, answer: str) -> Step:
            from bussola.profile.models import WorkProfile
            return Step("recap", "Ecco il tuo profilo.", recap=WorkProfile(pseudonym_id="P-1"))

    token = REGISTRY.create(RecapInterview(), on_evict=lambda: None)
    r = TestClient(create_app()).post(
        "/kiosk/interview/submit", json={"session_token": token, "answer": "x"}, headers=_h()
    )
    assert r.status_code == 200
    body = r.json()["step"]
    assert body["kind"] == "recap"
    assert body["recap"]["pseudonym_id"] == "P-1"
    REGISTRY.discard(token)
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/interview/test_interview.py -k recap tests/api/kiosk/test_interview_endpoints.py -k recap -q` → FAIL.

- [ ] **Step 3: Implement**

In `interview.py`, extend the `Step` dataclass:
```python
@dataclass(frozen=True)
class Step:
    kind: str  # question | summary | clarification | refusal | unavailable | completed | recap
    text: str
    recap: WorkProfile | None = None
```

Add `self._awaiting_recap = False` in `__init__` and reset it (=False) in `start`/`start_on`/`start_followup`.

Change `_finalize` so that after the incongruence check passes it enters the recap instead of completing directly. Replace the final `return self._complete()` in `_finalize` with `return self._enter_recap()`, and in the awaiting-final-clarification branch of `_submit` replace `return self._complete()` with `return self._enter_recap()`. Add:
```python
    def _enter_recap(self) -> Step:
        session = self._session
        assert session is not None
        self._awaiting_recap = True
        return Step("recap", _recap_intro(self._language), recap=session.profile)
```
Add the static intro (5 languages), mirroring `_final_summary`:
```python
def _recap_intro(language: str) -> str:
    messages = {
        "it": "Ecco cosa ho capito del tuo profilo. Controlla che sia giusto.",
        "en": "Here's what I understood about your profile. Please check it's right.",
        "fr": "Voici ce que j'ai compris de ton profil. Vérifie que c'est correct.",
        "es": "Esto es lo que he entendido de tu perfil. Comprueba que esté bien.",
        "ar": "هذا ما فهمته عن ملفك. تحقّق من أنه صحيح.",
    }
    return messages.get(language, messages["en"])
```

In `kiosk/routers/interview.py`, extend `StepOut` and the 3 constructions:
```python
class StepOut(BaseModel):
    kind: str
    text: str
    recap: WorkProfile | None = None
```
(import `from bussola.profile.models import WorkProfile`) and change each `StepOut(kind=step.kind, text=step.text)` → `StepOut(kind=step.kind, text=step.text, recap=step.recap)`.

- [ ] **Step 4: Run to verify pass + no regressions**

Run: `python -m pytest tests/interview/ tests/api/kiosk/ -q` → PASS. (Note: existing full-interview tests that asserted `kind == "completed"` at the end must be updated to expect `kind == "recap"` — the interview now ends at the recap, not `completed`. Complete happens only after the person confirms the recap, tested in Task 4.)

- [ ] **Step 5: Commit**

```bash
git add backend/src/bussola/interview/interview.py backend/src/bussola/api/kiosk/routers/interview.py backend/tests/interview/test_interview.py backend/tests/api/kiosk/test_interview_endpoints.py
git commit -m "feat(interview): il colloquio termina con un recap che porta il profilo salvato"
```

---

### Task 4: Recap confirm / correct (routing della correzione)

**Files:**
- Modify: `backend/src/bussola/interview/clarify.py` (add `apply_recap_correction`)
- Modify: `backend/src/bussola/interview/interview.py` (`_submit` recap branch)
- Test: `backend/tests/interview/test_clarify.py`, `backend/tests/interview/test_interview.py`

**Interfaces:**
- Consumes: `interpret_confirmation`, `extract_section`, `SECTIONS`, `session.merge`, `repo.save`.
- Produces: `apply_recap_correction(client: LlmClient, reply: str, profile: WorkProfile, language: str) -> BaseModel | None` (the corrected section extraction, or None if not routable).

- [ ] **Step 1: Write the failing tests**

```python
# test_clarify.py
from bussola.interview.clarify import apply_recap_correction
from bussola.interview.sections import ExperiencesExtraction

def test_apply_recap_correction_routes_and_reextracts():
    exp = {"experiences": [{"role": "consulente", "sector": "IT", "duration_months": 24}]}
    client = _Json([{"section": "experiences"}, exp])  # classify -> experiences ; re-extract
    out = apply_recap_correction(client, "il consulente era 2 anni non 2 mesi", WorkProfile(pseudonym_id="P-1"), "it")
    assert isinstance(out, ExperiencesExtraction)
    assert out.experiences[0].role == "consulente" and out.experiences[0].duration_months == 24

def test_apply_recap_correction_none_when_unroutable():
    client = _Json([{"section": "none"}])
    assert apply_recap_correction(client, "boh", WorkProfile(pseudonym_id="P-1"), "it") is None
```

```python
# test_interview.py — recap confirm completes; recap correction re-shows the recap
def test_recap_confirm_completes(make_fake_json_llm):
    repo = FakeRepo()
    json_responses, text_responses = [], []
    _confirm_all_sections(json_responses, text_responses)
    json_responses.append({"has_incongruence": False, "clarification": ""})
    json_responses.append({"confirmed": True})  # recap confirm
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    for _ in range(5):
        itw.submit("una risposta di lavoro"); itw.submit("sì, è corretto")
    assert itw.submit("sì, è tutto giusto").kind == "completed"

def test_recap_correction_reextracts_and_reshows(make_fake_json_llm):
    repo = FakeRepo()
    json_responses, text_responses = [], []
    _confirm_all_sections(json_responses, text_responses)
    json_responses.append({"has_incongruence": False, "clarification": ""})
    json_responses.append({"confirmed": False})  # not a confirmation -> correction
    json_responses.append({"section": "experiences"})  # routing
    json_responses.append({"experiences": [{"role": "consulente", "sector": "IT", "duration_months": 24}]})  # re-extract
    client = make_fake_json_llm(json_responses=json_responses, text_responses=[*text_responses, ALLOW])  # guard on the correction
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    for _ in range(5):
        itw.submit("una risposta di lavoro"); itw.submit("sì, è corretto")
    step = itw.submit("no, il consulente era 2 anni")
    assert step.kind == "recap"
    assert any(e.role == "consulente" and e.duration_months == 24 for e in step.recap.experiences)
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/interview/test_clarify.py -k recap_correction tests/interview/test_interview.py -k recap -q` → FAIL.

- [ ] **Step 3: Implement**

In `clarify.py`, add:
```python
from bussola.interview.extraction import extract_section

_ROUTE_SCHEMA = {
    "type": "object",
    "properties": {"section": {"type": "string",
        "enum": ["skills", "experiences", "aspirations", "constraints", "preferences", "none"]}},
    "required": ["section"],
    "additionalProperties": False,
}
_SECTION_BY_KEY = {s.key: s for s in SECTIONS}


def apply_recap_correction(
    client: LlmClient, reply: str, profile: WorkProfile, language: str
) -> BaseModel | None:
    """Route a free-text recap correction to a section and return its corrected
    extraction (constrained), or None if not routable/on error (§3 fail-closed:
    the caller keeps the recap unchanged)."""
    try:
        routed = client.chat_json(
            [
                {"role": "system", "content": (
                    "Which ONE profile section does this correction change? "
                    "Reply JSON {\"section\": one of "
                    "skills|experiences|aspirations|constraints|preferences|none}. "
                    "Use 'none' if it does not clearly map to a section.")},
                {"role": "user", "content": f"[current profile]\n{profile.model_dump_json()}\n[correction]\n{reply}"},
            ],
            json_schema=_ROUTE_SCHEMA,
        )
    except Exception:
        return None
    key = routed.get("section")
    section = _SECTION_BY_KEY.get(key) if isinstance(key, str) else None
    if section is None:
        return None
    # Re-extract the whole section from current data + the correction (extract_section
    # OVERWRITES the section via session.merge's first-interview semantics).
    context = (
        f"The person's current {section.key} is: {profile.model_dump_json()}. "
        f"They now correct it: {reply}. Produce the corrected {section.key}."
    )
    try:
        return extract_section(client, section, context, language)
    except Exception:
        return None
```

In `interview.py` `_submit`, add a branch BEFORE `_awaiting_confirmation` (and before the section-clarification branch is fine too; recap is terminal state):
```python
        if self._awaiting_recap:
            if interpret_confirmation(self._client, answer, self._language):
                self._awaiting_recap = False
                return self._complete()
            decision = self._guard.check(answer, self._language, question=_recap_intro(self._language))
            if not decision.allow:
                return Step("refusal", refusal_message(decision.category or RefusalCategory.OUT_OF_SCOPE, self._language))
            extracted = apply_recap_correction(self._client, answer, session.profile, self._language)
            if extracted is None:
                # not routable: keep the recap, ask to rephrase (static message)
                return Step("recap", _recap_retry(self._language), recap=session.profile)
            session.merge(extracted)
            self._repo.save(session.profile)
            return Step("recap", _recap_intro(self._language), recap=session.profile)
```
Add import `from bussola.interview.clarify import find_section_clarification, apply_recap_correction` (extend the Task-2 import) and `from bussola.interview.confirm import interpret_confirmation, summarize` (already imported). Add the static retry message:
```python
def _recap_retry(language: str) -> str:
    messages = {
        "it": "Non ho capito la correzione. Puoi ridirla in modo semplice?",
        "en": "I didn't catch that correction. Can you say it again simply?",
        "fr": "Je n'ai pas compris la correction. Peux-tu la redire simplement ?",
        "es": "No he entendido la corrección. ¿Puedes repetirla de forma sencilla?",
        "ar": "لم أفهم التصحيح. هل يمكنك إعادته ببساطة؟",
    }
    return messages.get(language, messages["en"])
```

Note: `session.merge` on the completed `InterviewSession` (first-interview) OVERWRITES the section from the extraction — correct for a recap edit.

- [ ] **Step 4: Run to verify pass + full suite**

Run: `python -m pytest tests/interview/ -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/bussola/interview/clarify.py backend/src/bussola/interview/interview.py backend/tests/interview/
git commit -m "feat(interview): recap confermabile + correzione a voce instradata alla sezione"
```

---

### Task 5: Kiosk — Step type, client, machine, App wiring for `recap`

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/App.tsx`, `frontend/src/state/kioskMachine.ts` (verify), `frontend/src/state/kioskMachine.test.ts`
- Test: `frontend/src/state/kioskMachine.test.ts`

**Interfaces:**
- Consumes: backend `recap` StepKind + `step.recap` payload.
- Produces: `StepKind` includes `'recap'`; `Step.recap?: WorkProfileView`; App renders `<Recap>` for `screen === 'recap'`.

- [ ] **Step 1: Write the failing test** (kioskMachine): a `submitted` step of kind `recap` maps to the `recap` screen and carries the payload.

```typescript
test('submitted recap maps to the recap screen and keeps the profile payload', () => {
  const base = { ...initialState, sessionToken: 'tok', pending: true }
  const profile = { pseudonym_id: 'P-1', skills: [], languages: [], experiences: [], desired_training: [], operational_notes: [], aspiration: null, digital_literacy: null }
  const s = reducer(base, { type: 'submitted', result: { status: 'ok', step: { kind: 'recap', text: 'Ecco', recap: profile } } })
  expect(s.screen).toBe('recap')
  expect(s.step?.recap?.pseudonym_id).toBe('P-1')
})
```

- [ ] **Step 2: Run to verify fail**

Run: `cd frontend && npm test -- --run src/state/kioskMachine.test.ts` → FAIL (type `'recap'` not assignable) / assertion fails.

- [ ] **Step 3: Implement**

In `types.ts`:
```typescript
export type StepKind =
  | 'question' | 'summary' | 'clarification' | 'refusal' | 'unavailable' | 'completed' | 'recap'

// Minimal view of the work profile shown at the recap (person's own data).
export interface WorkProfileView {
  pseudonym_id: string
  languages: { language: string; level: string }[]
  digital_literacy: string | null
  skills: { name: string; kind: string; evidence: string }[]
  experiences: { role: string; sector: string; duration_months: number }[]
  aspiration: { fields_of_interest: string[]; availability: string | null; constraints: string[] } | null
  desired_training: { topic: string }[]
  operational_notes: string[]
}

export interface Step {
  kind: StepKind
  text: string
  recap?: WorkProfileView
}
```
`kioskMachine.ts` already maps `step.kind`→screen via `screenFor` (identity) and stores `state.step = r.step`; `Screen` already includes `StepKind`, so `'recap'` is covered — no reducer change needed beyond the type. Verify `nextPrompt`'s `PROMPT_KINDS` does NOT include `'recap'` (the recap is not a re-showable prompt); leave as is.

In `App.tsx` `renderScreen`, add:
```tsx
      case 'recap':
        return <Recap key={state.stepSeq} profile={state.step!.recap!} onSubmit={submit} busy={state.pending} />
```
and `import { Recap } from './screens/Recap'`.

- [ ] **Step 4: Run to verify pass**

Run: `npm test -- --run src/state/kioskMachine.test.ts && npm run typecheck` → PASS (typecheck will fail until Task 6 creates `Recap`; create a minimal stub `Recap.tsx` in Task 6, or land Task 5+6 together).

- [ ] **Step 5: Commit** (together with Task 6 if typecheck needs the component)

```bash
git add frontend/src/types.ts frontend/src/App.tsx frontend/src/state/kioskMachine.test.ts
git commit -m "feat(kiosk): tipo Step.recap + instradamento schermata recap"
```

---

### Task 6: Kiosk — `Recap` screen + i18n labels (5 lingue) + a11y

**Files:**
- Create: `frontend/src/screens/Recap.tsx`
- Modify: `frontend/src/i18n/locales/{it,en,fr,es,ar}.ts` (add a `recap` block)
- Test: `frontend/src/screens/Recap.test.tsx`, `frontend/src/a11y.audit.test.tsx`

**Interfaces:**
- Consumes: `WorkProfileView` (Task 5), `ConfirmCorrect` pattern, `VoiceBar`, `BigButton`.
- Produces: `Recap({ profile, onSubmit, busy })` — renders labeled sections + Sì/Correggi; VoiceBar reads a composed text.

- [ ] **Step 1: Write the failing test**

```tsx
// Recap.test.tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Recap } from './Recap'
import i18n from '../i18n'

const PROFILE = {
  pseudonym_id: 'P-1', languages: [{ language: 'it', level: 'fluent' }], digital_literacy: 'basic',
  skills: [{ name: 'cucina', kind: 'technical', evidence: 'stated' }],
  experiences: [{ role: 'consulente', sector: 'IT', duration_months: 24 }],
  aspiration: { fields_of_interest: ['ristorazione'], availability: 'full_time', constraints: [] },
  desired_training: [{ topic: 'HACCP' }], operational_notes: [],
}

test('shows the profile fields (role + person words) and confirms', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Recap profile={PROFILE} onSubmit={onSubmit} />, { language: 'it' })
  expect(screen.getByText('consulente')).toBeInTheDocument()
  expect(screen.getByText('cucina')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è tutto giusto' }))
  expect(onSubmit).toHaveBeenCalled()
})

test('correcting sends the free text', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Recap profile={PROFILE} onSubmit={onSubmit} />, { language: 'it' })
  await userEvent.click(screen.getByRole('button', { name: 'Correggi qualcosa' }))
  await userEvent.type(screen.getByRole('textbox'), 'il consulente era 2 anni')
  await userEvent.click(screen.getByRole('button', { name: 'Invia la correzione' }))
  expect(onSubmit).toHaveBeenCalledWith('il consulente era 2 anni')
})
```

- [ ] **Step 2: Run to verify fail**

Run: `npm test -- --run src/screens/Recap.test.tsx` → FAIL (no `Recap`).

- [ ] **Step 3: Implement**

Add a `recap` block to EACH of the 5 locale files with: `title`, `confirm` ("Sì, è tutto giusto" / …), `correct` ("Correggi qualcosa" / …), `send` ("Invia la correzione" / …), section headers (`skills`, `languages`, `digitalLiteracy`, `experiences`, `aspiration`, `training`, `constraints`, `notes`, `none` = "—"), a `months` template (`"{{n}} mesi"`), and value maps for the enums (`level_*`, `digital_*`, `evidence_*`, `kind_*`, `availability_*`, `constraint_*`, `note_*`) mirroring the operator-portal `pl.*` block, translated into each language. Keep ar wording provisional (native-speaker review is a known follow-up).

`Recap.tsx`:
```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { VoiceBar } from '../components/VoiceBar'
import type { WorkProfileView } from '../types'

export function Recap({ profile, onSubmit, busy }: { profile: WorkProfileView; onSubmit: (a: string) => void; busy?: boolean }) {
  const { t } = useTranslation()
  const [correcting, setCorrecting] = useState(false)
  const [value, setValue] = useState('')
  const [voiceBusy, setVoiceBusy] = useState(false)
  const trimmed = value.trim()

  const lines: string[] = []
  const push = (label: string, val: string) => { if (val) lines.push(`${label}: ${val}`) }
  push(t('recap.skills'), profile.skills.map((s) => s.name).join(', '))
  push(t('recap.languages'), profile.languages.map((l) => `${l.language} (${t('recap.level_' + l.level)})`).join(', '))
  if (profile.digital_literacy) push(t('recap.digitalLiteracy'), t('recap.digital_' + profile.digital_literacy))
  push(t('recap.experiences'), profile.experiences.map((e) => `${e.role} — ${e.sector} — ${t('recap.months', { n: e.duration_months })}`).join('; '))
  if (profile.aspiration) {
    push(t('recap.aspiration'), profile.aspiration.fields_of_interest.join(', '))
    if (profile.aspiration.availability) push(t('recap.availability'), t('recap.availability_' + profile.aspiration.availability))
    push(t('recap.constraints'), profile.aspiration.constraints.map((c) => t('recap.constraint_' + c)).join(', '))
  }
  push(t('recap.training'), profile.desired_training.map((d) => d.topic).join(', '))
  push(t('recap.notes'), profile.operational_notes.map((n) => t('recap.note_' + n)).join(', '))
  const spoken = [t('recap.title'), ...lines].join('. ')

  return (
    <div className="recap">
      <h1>{t('recap.title')}</h1>
      {!correcting ? (
        <>
          <VoiceBar text={spoken} disabled={busy} />
          <ul className="recap-list">
            {lines.map((line) => <li key={line}>{line}</li>)}
          </ul>
          <BigButton variant="confirm" disabled={busy} onClick={() => onSubmit(t('recap.confirm'))}>{t('recap.confirm')}</BigButton>
          <BigButton variant="secondary" disabled={busy} onClick={() => setCorrecting(true)}>{t('recap.correct')}</BigButton>
        </>
      ) : (
        <>
          <VoiceBar text={spoken} canDictate onDictated={setValue} onBusyChange={setVoiceBusy} disabled={busy} />
          <textarea aria-label={t('recap.correctPlaceholder')} placeholder={t('recap.correctPlaceholder')}
            value={value} disabled={voiceBusy || busy} onChange={(e) => setValue(e.target.value)} />
          <BigButton variant="confirm" disabled={!trimmed || busy || voiceBusy} onClick={() => onSubmit(trimmed)}>{t('recap.send')}</BigButton>
        </>
      )}
    </div>
  )
}
```
Add `recap.correctPlaceholder` to the 5 locales too. Note: the labeled `<li>` text renders the person's OWN words (skill names, role, sector, topic) verbatim and the enum values via i18n — matching the operator's structured view but accessible + voice-read.

- [ ] **Step 4: Add an a11y audit case** (in `a11y.audit.test.tsx`)

```tsx
test('Recap has no a11y violations', async () => {
  const { container } = renderWithProviders(<Recap profile={{ pseudonym_id: 'P-1', languages: [], digital_literacy: null, skills: [], experiences: [], aspiration: null, desired_training: [], operational_notes: [] }} onSubmit={() => {}} />)
  await expectNoA11yViolations(container)
})
```
(import `Recap`.)

- [ ] **Step 5: Run to verify pass + full kiosk gate**

Run: `npm test -- --run && npm run typecheck && npm run lint && npm run build` → all PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/Recap.tsx frontend/src/screens/Recap.test.tsx frontend/src/i18n/locales/ frontend/src/a11y.audit.test.tsx
git commit -m "feat(kiosk): schermata Recap (lista a etichette 5 lingue + voce + correzione)"
```

---

### Task 7: STATO_TECNICO + full gate

**Files:**
- Modify: `STATO_TECNICO.md`

- [ ] **Step 1:** Add a decision row (next Sott. number) summarizing the recap + per-section clarification (§5/§7.1 realized, no nucleus change), noting the recap-correction routing as the LLM-dependent piece to validate live, and ar strings pending native review.
- [ ] **Step 2:** Run the FULL gates: backend `pytest -q` + `ruff check .` + `ruff format --check .` + `mypy src`; kiosk `npm test -- --run` + `typecheck` + `lint` + `build`. All green.
- [ ] **Step 3: Commit**

```bash
git add STATO_TECNICO.md
git commit -m "docs(stato-tecnico): registra recap finale + chiarimento aperto"
```

---

## Self-Review

**Spec coverage:** (1) per-section clarification = Tasks 1–2 (fail-open, max 1/section, coherence via profile-so-far); (2) recap schematic no-LLM = Task 3 (payload) + Task 6 (kiosk render+voice), free-text correction routing = Task 4; (3) incongruence unchanged = untouched (Task 3 keeps `find_incongruence` before the recap). Step contract change = Task 3+5. i18n 5 langs = Task 6. Testing/degrade = each task's tests + Task 7 gate. ✅ all covered.

**Placeholder scan:** no TBD/TODO; every step has concrete code. ✅

**Type consistency:** `find_section_clarification(client, section, extracted, profile, language) -> str|None`; `apply_recap_correction(client, reply, profile, language) -> BaseModel|None`; `Step.recap: WorkProfile|None`; `StepOut.recap: WorkProfile|None`; `WorkProfileView` fields mirror `WorkProfile`. Section keys used in `_ROUTE_SCHEMA` match `SECTIONS` keys (skills/experiences/aspirations/constraints/preferences). ✅

**Note for the implementer:** Task 2/3 require updating `_confirm_all_sections` (add a `needs_clarification:false` json per section) and the existing end-of-interview tests (now end at `recap`, not `completed`). These are called out in the task bodies.
