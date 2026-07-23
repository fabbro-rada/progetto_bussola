# Piano — Sottosistema 4: Ciclo centrale del colloquio

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Motore conversazionale backend che conduce un colloquio a tappe, estrae dati validati verso lo schema `WorkProfile`, fa confermare la persona, chiarisce le incongruenze e persiste un profilo realistico.

**Architecture:** Package `bussola.interview`: macchina a stati deterministica (l'app conduce) che usa l'LLM (S3) per formulare domande, estrarre (constrained decoding), riepilogare, verificare incongruenze; integra guardrail (S3), profilo whitelist (S1), persistenza+audit (S2). Unit con LLM finto; integrazione con Qwen2.5 reale.

**Tech Stack:** Python 3.12, Pydantic (schema + json_schema), httpx (client LLM esteso con output vincolato), pytest.

## Global Constraints

- **Il sistema conduce** (§7.1): flusso deterministico app-driven; l'LLM non decide la progressione.
- **Estrazione strutturata validata** (§7.3): constrained decoding (json_schema) + Pydantic `extra="forbid"`; il profilo resta **solo-lavoro** per costruzione.
- **Conferma dalla persona** (§5): riepilogo → conferma/correzione a fine sezione e fine colloquio. Chi conferma è la persona, non l'operatore.
- **Incongruenze** (§5): controllo LLM semantico → domanda di chiarimento **gentile, non giudicante** (§4).
- **Guardrail su ogni risposta libera** (§2/§7.3): `ScopeGuard`; fuori-tema/injection → rifiuto gentile e ri-poni la domanda.
- **Degrado elegante** (§3/§7.1): su `LlmUnavailable`/errore imprevisto → passo controllato, mai crash; le sezioni confermate restano persistite.
- **Persistenza per-sezione** via `ProfileRepository.save` (ri-applica il filtro PII); `append_audit` con `actor=None`.
- **TDD**; **solo dati sintetici**; **codice in inglese** (§11); i messaggi/domande utente **localizzati** (5 lingue).
- **Gate:** `ruff check` + `ruff format --check` + `mypy` puliti sui file toccati.
- **Shell state non persiste tra chiamate Bash:** usare `backend/.venv/bin/...` (assoluti).

---

## Struttura dei file

```
backend/src/bussola/
├── llm/client.py                       # + chat_json(...) output vincolato (json_schema)
└── interview/
    ├── __init__.py
    ├── sections.py                     # Section (5 tappe): extraction model, domanda i18n, prompt
    ├── session.py                      # InterviewSession + merge nel WorkProfile parziale
    ├── extraction.py                   # extract_section (constrained + Pydantic)
    ├── confirm.py                      # summarize + interpret_confirmation
    ├── incongruence.py                 # find_incongruence
    └── interview.py                    # Interview: start/submit -> Step (orchestratore)
backend/tests/
├── llm/test_client_json.py
└── interview/
    ├── conftest.py                     # FakeJsonLlmClient, fake ProfileRepository, personas sintetiche
    ├── test_sections.py
    ├── test_session.py
    ├── test_extraction.py
    ├── test_confirm.py
    ├── test_incongruence.py
    ├── test_interview.py               # flusso con LLM finto + fake repo
    └── test_interview_live.py          # integrazione end-to-end, requires_llm + DB
```

---

### Task 1: Client LLM — output JSON vincolato (`chat_json`)

**Files:**
- Modify: `backend/src/bussola/llm/client.py` (aggiunge `chat_json` a `LlmClient` e `HttpxLlmClient`)
- Test: `backend/tests/llm/test_client_json.py`

**Interfaces:**
- Consumes: `HttpxLlmClient` (S3).
- Produces: `LlmClient.chat_json(messages: list[dict[str, str]], *, json_schema: dict[str, Any], temperature: float = 0.0, max_tokens: int | None = None) -> dict[str, Any]` — invia `response_format={"type":"json_schema","json_schema":{"name":"extraction","schema":<schema>,"strict":true}}` a llama-server e ritorna il JSON già parsato; `LlmUnavailable` su timeout.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/llm/test_client_json.py`:

```python
import httpx
import pytest

from bussola.llm.client import HttpxLlmClient, LlmUnavailable


def test_chat_json_sends_schema_and_parses_object():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"ok": true, "n": 2}'}}]}
        )

    client = HttpxLlmClient(
        base_url="http://test", model="m", transport=httpx.MockTransport(handler)
    )
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    out = client.chat_json([{"role": "user", "content": "hi"}], json_schema=schema)
    assert out == {"ok": True, "n": 2}
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["body"]["response_format"]["json_schema"]["schema"] == schema


def test_chat_json_timeout_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    client = HttpxLlmClient(
        base_url="http://test", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailable):
        client.chat_json([{"role": "user", "content": "hi"}], json_schema={"type": "object"})
```

- [ ] **Step 2: Eseguire (deve fallire)**

Run: `backend/.venv/bin/pytest backend/tests/llm/test_client_json.py -q`
Expected: FAIL (`chat_json` inesistente).

- [ ] **Step 3: Implementare**

Aggiungere al `Protocol` `LlmClient` in `backend/src/bussola/llm/client.py` la firma:

```python
    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]: ...
```

Aggiungere al `HttpxLlmClient` il metodo:

```python
    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Chat with a JSON-schema-constrained response; returns the parsed object."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "schema": json_schema, "strict": True},
            },
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        try:
            response = self._client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.TransportError as exc:
            raise LlmUnavailable(str(exc)) from exc
        data = response.json()
        content: str = data["choices"][0]["message"]["content"]
        parsed: dict[str, Any] = json.loads(content)
        return parsed
```

Aggiungere `import json` in cima al file (dopo gli import esistenti).

- [ ] **Step 4: Eseguire (deve passare)**

Run: `backend/.venv/bin/pytest backend/tests/llm/test_client_json.py -q`
Expected: PASS (2 test).

- [ ] **Step 5: Committare**

```bash
git add backend/src/bussola/llm/client.py backend/tests/llm/test_client_json.py
git commit -m "feat(llm): chat_json con output vincolato da json_schema"
```

---

### Task 2: Sezioni del colloquio (`sections.py`) + domande i18n

**Files:**
- Create: `backend/src/bussola/interview/__init__.py` (vuoto), `backend/src/bussola/interview/sections.py`
- Test: `backend/tests/interview/test_sections.py`

**Interfaces:**
- Consumes: modelli foglia S1 (`Skill`, `LanguageKnown`, `WorkExperience`, `DesiredTraining`, enum).
- Produces: `Section` (dataclass: `key: str`, `extraction_model: type[BaseModel]`, `base_question: dict[str, str]` per 5 lingue, `extraction_prompt: str`); `SECTIONS: tuple[Section, ...]` (ordine fisso: competenze, esperienze, aspirazioni, vincoli, preferenze); `base_question(section, language) -> str` (fallback en). Modelli di estrazione: `SkillsExtraction`, `ExperiencesExtraction`, `AspirationsExtraction`, `ConstraintsExtraction`, `PreferencesExtraction` (Pydantic, `extra="forbid"`, riusano i modelli foglia S1).

- [ ] **Step 1: Scrivere i test (falliscono)**

File `backend/tests/interview/test_sections.py`:

```python
from bussola.interview.sections import SECTIONS, base_question


def test_five_sections_in_fixed_order():
    keys = [s.key for s in SECTIONS]
    assert keys == ["competenze", "esperienze", "aspirazioni", "vincoli", "preferenze"]


def test_every_section_has_all_five_languages():
    for section in SECTIONS:
        for lang in ("it", "en", "fr", "es", "ar"):
            assert section.base_question[lang].strip()


def test_base_question_falls_back_to_english():
    assert base_question(SECTIONS[0], "de") == SECTIONS[0].base_question["en"]


def test_extraction_models_forbid_extra_fields():
    import pytest
    from pydantic import ValidationError

    model = SECTIONS[0].extraction_model
    with pytest.raises(ValidationError):
        model(secret="x")
```

- [ ] **Step 2: Eseguire (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_sections.py -q`
Expected: FAIL (`bussola.interview.sections` inesistente).

- [ ] **Step 3: Implementare**

File `backend/src/bussola/interview/__init__.py`: (vuoto)

File `backend/src/bussola/interview/sections.py`:

```python
"""Declarative interview sections. The app drives these in fixed order; the LLM
fills each section's extraction model (constrained), never the flow."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from bussola.profile.enums import Availability, DigitalLiteracy, OperationalNoteCategory, WorkConstraint
from bussola.profile.models import DesiredTraining, LanguageKnown, Skill, WorkExperience

_STRICT = ConfigDict(extra="forbid")


class SkillsExtraction(BaseModel):
    model_config = _STRICT
    skills: list[Skill] = Field(default_factory=list)
    languages: list[LanguageKnown] = Field(default_factory=list)
    digital_literacy: DigitalLiteracy | None = None


class ExperiencesExtraction(BaseModel):
    model_config = _STRICT
    experiences: list[WorkExperience] = Field(default_factory=list)


class AspirationsExtraction(BaseModel):
    model_config = _STRICT
    fields_of_interest: list[str] = Field(default_factory=list, max_length=20)
    desired_training: list[DesiredTraining] = Field(default_factory=list)


class ConstraintsExtraction(BaseModel):
    model_config = _STRICT
    availability: Availability | None = None
    constraints: list[WorkConstraint] = Field(default_factory=list)


class PreferencesExtraction(BaseModel):
    model_config = _STRICT
    operational_notes: list[OperationalNoteCategory] = Field(default_factory=list)


@dataclass(frozen=True)
class Section:
    key: str
    extraction_model: type[BaseModel]
    base_question: dict[str, str]
    extraction_prompt: str


SECTIONS: tuple[Section, ...] = (
    Section(
        "competenze",
        SkillsExtraction,
        {
            "it": "Parlami delle tue competenze: cosa sai fare bene, con le mani o con le persone? E che lingue parli?",
            "en": "Tell me about your skills: what are you good at, with your hands or with people? And which languages do you speak?",
            "fr": "Parle-moi de tes compétences : qu'est-ce que tu sais bien faire, manuellement ou avec les gens ? Et quelles langues parles-tu ?",
            "es": "Háblame de tus competencias: ¿qué se te da bien, con las manos o con las personas? ¿Y qué idiomas hablas?",
            "ar": "حدثني عن مهاراتك: ما الذي تجيده، بيديك أو مع الناس؟ وما اللغات التي تتحدثها؟",
        },
        "Extract the person's skills (technical/soft, with an evidence grade), known languages with level, and digital literacy, from their reply. Only what they actually said.",
    ),
    Section(
        "esperienze",
        ExperiencesExtraction,
        {
            "it": "Che lavori hai fatto finora? Anche brevi. Per ognuno: che ruolo, in che settore, per quanto tempo.",
            "en": "What jobs have you done so far? Even short ones. For each: which role, which sector, for how long.",
            "fr": "Quels métiers as-tu exercés jusqu'ici ? Même courts. Pour chacun : quel rôle, quel secteur, combien de temps.",
            "es": "¿Qué trabajos has hecho hasta ahora? Aunque sean cortos. Para cada uno: qué puesto, en qué sector, cuánto tiempo.",
            "ar": "ما الأعمال التي قمت بها حتى الآن؟ حتى القصيرة منها. لكل عمل: ما الدور، وفي أي قطاع، وكم من الوقت.",
        },
        "Extract past work experiences (role, sector, duration in months) from their reply. Only what they actually said.",
    ),
    Section(
        "aspirazioni",
        AspirationsExtraction,
        {
            "it": "Che tipo di lavoro ti piacerebbe fare? E c'è qualche formazione o corso che vorresti seguire?",
            "en": "What kind of work would you like to do? And is there any training or course you'd like to take?",
            "fr": "Quel type de travail aimerais-tu faire ? Et y a-t-il une formation ou un cours que tu voudrais suivre ?",
            "es": "¿Qué tipo de trabajo te gustaría hacer? ¿Y hay alguna formación o curso que quisieras hacer?",
            "ar": "ما نوع العمل الذي تود القيام به؟ وهل هناك تدريب أو دورة ترغب في حضورها؟",
        },
        "Extract fields of interest and desired training topics from their reply. Only what they actually said.",
    ),
    Section(
        "vincoli",
        ConstraintsExtraction,
        {
            "it": "Ci sono vincoli pratici sul lavoro? Per esempio disponibilità di tempo (pieno, parziale, flessibile) o turni.",
            "en": "Are there practical work constraints? For example time availability (full-time, part-time, flexible) or shifts.",
            "fr": "Y a-t-il des contraintes pratiques pour le travail ? Par exemple la disponibilité (temps plein, partiel, flexible) ou les horaires.",
            "es": "¿Hay limitaciones prácticas para el trabajo? Por ejemplo disponibilidad (completa, parcial, flexible) o turnos.",
            "ar": "هل هناك قيود عملية على العمل؟ مثل التفرغ (دوام كامل، جزئي، مرن) أو المناوبات.",
        },
        "Extract availability (full_time/part_time/flexible) and work-scheduling constraints from their reply. Never health or juridical items. Only what they actually said.",
    ),
    Section(
        "preferenze",
        PreferencesExtraction,
        {
            "it": "Un'ultima cosa: preferisci lavorare in squadra o da solo? C'è qualcosa che ti aiuterebbe a partire meglio (es. supporto con la lingua)?",
            "en": "One last thing: do you prefer working in a team or alone? Is there anything that would help you start better (e.g. language support)?",
            "fr": "Une dernière chose : préfères-tu travailler en équipe ou seul ? Y a-t-il quelque chose qui t'aiderait à mieux démarrer (ex. soutien linguistique) ?",
            "es": "Una última cosa: ¿prefieres trabajar en equipo o solo? ¿Hay algo que te ayudaría a empezar mejor (p. ej. apoyo con el idioma)?",
            "ar": "أمر أخير: هل تفضل العمل ضمن فريق أم بمفردك؟ هل هناك ما قد يساعدك على بداية أفضل (مثل دعم اللغة)؟",
        },
        "Extract operational notes ONLY from the closed set (needs_language_support, needs_literacy_support, limited_availability, prefers_team_work, prefers_solo_work) from their reply.",
    ),
)


def base_question(section: Section, language: str) -> str:
    """Return the section's base question in `language` (fallback: English)."""
    return section.base_question.get(language, section.base_question["en"])
```

- [ ] **Step 4: Eseguire (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_sections.py -q`
Expected: PASS (4 test).

- [ ] **Step 5: Committare**

```bash
git add backend/src/bussola/interview/__init__.py backend/src/bussola/interview/sections.py backend/tests/interview/test_sections.py
git commit -m "feat(interview): definizione dichiarativa delle tappe + domande i18n"
```

---

### Task 3: Stato di sessione (`session.py`)

**Files:**
- Create: `backend/src/bussola/interview/session.py`
- Test: `backend/tests/interview/test_session.py`

**Interfaces:**
- Consumes: `WorkProfile` (S1), `SECTIONS` (Task 2), i modelli di estrazione (Task 2).
- Produces: `InterviewSession(pseudonym_id, language)` con: `.profile: WorkProfile`, `.section_index: int`, `.current_section -> Section | None`, `.merge(extracted: BaseModel) -> None` (applica i campi estratti al profilo parziale, gestendo l'`aspiration` composita), `.advance() -> None`, `.completed -> bool`.

- [ ] **Step 1: Scrivere i test (falliscono)**

File `backend/tests/interview/test_session.py`:

```python
from bussola.interview.sections import (
    AspirationsExtraction,
    SkillsExtraction,
    ConstraintsExtraction,
)
from bussola.interview.session import InterviewSession
from bussola.profile.enums import Availability, EvidenceGrade, SkillKind
from bussola.profile.models import Skill


def test_starts_at_first_section_with_empty_profile():
    s = InterviewSession("P-1", "it")
    assert s.current_section.key == "competenze"
    assert s.profile.pseudonym_id == "P-1"
    assert s.profile.skills == []
    assert s.completed is False


def test_merge_applies_extracted_fields():
    s = InterviewSession("P-1", "it")
    s.merge(
        SkillsExtraction(
            skills=[Skill(name="cooking", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)]
        )
    )
    assert s.profile.skills[0].name == "cooking"


def test_merge_composes_aspiration_across_sections():
    s = InterviewSession("P-1", "it")
    s.merge(AspirationsExtraction(fields_of_interest=["ristorazione"]))
    s.merge(ConstraintsExtraction(availability=Availability.PART_TIME))
    assert s.profile.aspiration is not None
    assert s.profile.aspiration.fields_of_interest == ["ristorazione"]
    assert s.profile.aspiration.availability is Availability.PART_TIME


def test_advance_and_completion():
    s = InterviewSession("P-1", "it")
    for _ in range(5):
        assert s.completed is False
        s.advance()
    assert s.completed is True
    assert s.current_section is None
```

- [ ] **Step 2: Eseguire (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_session.py -q`
Expected: FAIL (`session` inesistente).

- [ ] **Step 3: Implementare**

File `backend/src/bussola/interview/session.py`:

```python
"""In-memory interview session state. The confirmed WorkProfile is built up
section by section; the app persists it per confirmed section (see Interview)."""

from __future__ import annotations

from pydantic import BaseModel

from bussola.interview.sections import (
    SECTIONS,
    AspirationsExtraction,
    SkillsExtraction,
    ExperiencesExtraction,
    PreferencesExtraction,
    Section,
    ConstraintsExtraction,
)
from bussola.profile.models import Aspiration, WorkProfile


class InterviewSession:
    def __init__(self, pseudonym_id: str, language: str) -> None:
        self.language = language
        self.profile = WorkProfile(pseudonym_id=pseudonym_id)
        self.section_index = 0

    @property
    def current_section(self) -> Section | None:
        if self.section_index >= len(SECTIONS):
            return None
        return SECTIONS[self.section_index]

    @property
    def completed(self) -> bool:
        return self.section_index >= len(SECTIONS)

    def advance(self) -> None:
        self.section_index += 1

    def _aspiration(self) -> Aspiration:
        if self.profile.aspiration is None:
            self.profile.aspiration = Aspiration()
        return self.profile.aspiration

    def merge(self, extracted: BaseModel) -> None:
        """Apply an extracted section model to the partial profile."""
        if isinstance(extracted, SkillsExtraction):
            self.profile.skills = extracted.skills
            self.profile.languages = extracted.languages
            self.profile.digital_literacy = extracted.digital_literacy
        elif isinstance(extracted, ExperiencesExtraction):
            self.profile.experiences = extracted.experiences
        elif isinstance(extracted, AspirationsExtraction):
            asp = self._aspiration()
            asp.fields_of_interest = extracted.fields_of_interest
            self.profile.desired_training = extracted.desired_training
        elif isinstance(extracted, ConstraintsExtraction):
            asp = self._aspiration()
            asp.availability = extracted.availability
            asp.constraints = extracted.constraints
        elif isinstance(extracted, PreferencesExtraction):
            self.profile.operational_notes = extracted.operational_notes
        else:  # pragma: no cover - defensive
            raise TypeError(f"unknown extraction model: {type(extracted)!r}")
```

- [ ] **Step 4: Eseguire (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_session.py -q`
Expected: PASS (4 test).

- [ ] **Step 5: Committare**

```bash
git add backend/src/bussola/interview/session.py backend/tests/interview/test_session.py
git commit -m "feat(interview): stato di sessione con merge nel profilo parziale"
```

---

### Task 4: Estrazione per-sezione (`extraction.py`)

**Files:**
- Create: `backend/src/bussola/interview/extraction.py`
- Create: `backend/tests/interview/conftest.py` (LLM finto + persona)
- Test: `backend/tests/interview/test_extraction.py`

**Interfaces:**
- Consumes: `LlmClient.chat_json` (Task 1), `Section` (Task 2).
- Produces: `extract_section(client, section, answer, language) -> BaseModel` — chiama `client.chat_json` con lo `model_json_schema()` della sezione, valida col modello della sezione, ritorna l'istanza validata. Fail-safe: se il JSON non valida, ritorna un'istanza **vuota** della sezione (nessun dato inventato) — non solleva.
- Test support in `conftest.py`: `FakeJsonLlmClient(json_responses: list[dict])` con `.chat_json` che ritorna in ordine e `.calls`; fixture `make_fake_json_llm`.

- [ ] **Step 1: Scrivere conftest + test (falliscono)**

File `backend/tests/interview/conftest.py`:

```python
from __future__ import annotations

import pytest


class FakeJsonLlmClient:
    """Deterministic LLM double for constrained extraction + text calls."""

    def __init__(self, json_responses: list[dict] | None = None, text_responses: list[str] | None = None) -> None:
        self._json = list(json_responses or [])
        self._text = list(text_responses or [])
        self.calls: list[dict] = []

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None) -> dict:
        self.calls.append({"kind": "json", "messages": messages})
        if not self._json:
            raise AssertionError("FakeJsonLlmClient: no more json responses")
        return self._json.pop(0)

    def chat(self, messages, *, temperature=0.0, max_tokens=None) -> str:
        self.calls.append({"kind": "text", "messages": messages})
        if not self._text:
            raise AssertionError("FakeJsonLlmClient: no more text responses")
        return self._text.pop(0)


@pytest.fixture
def make_fake_json_llm():
    def _make(json_responses=None, text_responses=None) -> FakeJsonLlmClient:
        return FakeJsonLlmClient(json_responses, text_responses)

    return _make
```

File `backend/tests/interview/test_extraction.py`:

```python
from bussola.interview.extraction import extract_section
from bussola.interview.sections import SECTIONS


def test_extracts_and_validates_section(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[
        {"skills": [{"name": "cooking", "kind": "technical", "evidence": "demonstrated"}],
         "languages": [], "digital_literacy": None}
    ])
    result = extract_section(client, SECTIONS[0], "so cucinare", "it")
    assert result.skills[0].name == "cooking"


def test_invalid_extraction_is_fail_safe_empty(make_fake_json_llm):
    # extra field not in schema -> validation fails -> empty model (no invented data)
    client = make_fake_json_llm(json_responses=[{"unexpected": "x"}])
    result = extract_section(client, SECTIONS[0], "boh", "it")
    assert result.skills == []
    assert result.languages == []
```

- [ ] **Step 2: Eseguire (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_extraction.py -q`
Expected: FAIL (`extraction` inesistente).

- [ ] **Step 3: Implementare**

File `backend/src/bussola/interview/extraction.py`:

```python
"""Per-section extraction via constrained decoding + Pydantic validation.

Fail-safe: an unparseable/invalid model yields an EMPTY section model (no
invented data), never an exception — the flow can re-ask if needed.
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from bussola.interview.sections import Section
from bussola.llm.client import LlmClient


def extract_section(
    client: LlmClient, section: Section, answer: str, language: str
) -> BaseModel:
    schema = section.extraction_model.model_json_schema()
    raw = client.chat_json(
        [
            {"role": "system", "content": section.extraction_prompt},
            {"role": "user", "content": f"[reply, language={language}]\n{answer}"},
        ],
        json_schema=schema,
    )
    try:
        return section.extraction_model.model_validate(raw)
    except ValidationError:
        return section.extraction_model()  # fail-safe: empty, no invented data
```

- [ ] **Step 4: Eseguire (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_extraction.py -q`
Expected: PASS (2 test).

- [ ] **Step 5: Committare**

```bash
git add backend/src/bussola/interview/extraction.py backend/tests/interview/conftest.py backend/tests/interview/test_extraction.py
git commit -m "feat(interview): estrazione per-sezione con constrained decoding e fail-safe"
```

---

### Task 5: Riepilogo & conferma + incongruenze (`confirm.py`, `incongruence.py`)

**Files:**
- Create: `backend/src/bussola/interview/confirm.py`, `backend/src/bussola/interview/incongruence.py`
- Test: `backend/tests/interview/test_confirm.py`, `backend/tests/interview/test_incongruence.py`

**Interfaces:**
- Produces:
  - `summarize(client, section, extracted, language) -> str` — riassunto in linguaggio naturale (chat, nella lingua).
  - `interpret_confirmation(client, answer, language) -> bool` — True se la persona conferma, False se corregge/nega (chat_json con schema `{"confirmed": bool}`, fail-safe: False).
  - `find_incongruence(client, profile, language) -> str | None` — domanda di chiarimento gentile se c'è un'incongruenza semantica, altrimenti None (chat_json con `{"has_incongruence": bool, "clarification": str}`, fail-safe: None).

- [ ] **Step 1: Scrivere i test (falliscono)**

File `backend/tests/interview/test_confirm.py`:

```python
from bussola.interview.confirm import interpret_confirmation, summarize
from bussola.interview.sections import SECTIONS
from bussola.interview.sections import SkillsExtraction


def test_summarize_returns_text(make_fake_json_llm):
    client = make_fake_json_llm(text_responses=["Hai detto che sai cucinare."])
    text = summarize(client, SECTIONS[0], SkillsExtraction(), "it")
    assert "cucinare" in text


def test_interpret_confirmation_true(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{"confirmed": True}])
    assert interpret_confirmation(client, "sì esatto", "it") is True


def test_interpret_confirmation_false_and_failsafe(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{"confirmed": False}])
    assert interpret_confirmation(client, "no, ho detto altro", "it") is False
    client2 = make_fake_json_llm(json_responses=[{"weird": 1}])  # invalid -> fail-safe False
    assert interpret_confirmation(client2, "???", "it") is False
```

File `backend/tests/interview/test_incongruence.py`:

```python
from bussola.interview.incongruence import find_incongruence
from bussola.profile.models import WorkProfile


def test_incongruence_found(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[
        {"has_incongruence": True, "clarification": "Hai detto 10 anni come cuoco ma hai 20 anni: puoi chiarire?"}
    ])
    q = find_incongruence(client, WorkProfile(pseudonym_id="P-1"), "it")
    assert q and "chiarire" in q


def test_no_incongruence_and_failsafe(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{"has_incongruence": False, "clarification": ""}])
    assert find_incongruence(client, WorkProfile(pseudonym_id="P-1"), "it") is None
    client2 = make_fake_json_llm(json_responses=[{"broken": 1}])  # invalid -> fail-safe None
    assert find_incongruence(client2, WorkProfile(pseudonym_id="P-1"), "it") is None
```

- [ ] **Step 2: Eseguire (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_confirm.py backend/tests/interview/test_incongruence.py -q`
Expected: FAIL (moduli inesistenti).

- [ ] **Step 3: Implementare**

File `backend/src/bussola/interview/confirm.py`:

```python
"""Summary and confirmation. The PERSON confirms or corrects (§5)."""

from __future__ import annotations

from pydantic import BaseModel

from bussola.interview.sections import Section
from bussola.llm.client import LlmClient

_CONFIRM_SCHEMA = {
    "type": "object",
    "properties": {"confirmed": {"type": "boolean"}},
    "required": ["confirmed"],
    "additionalProperties": False,
}


def summarize(client: LlmClient, section: Section, extracted: BaseModel, language: str) -> str:
    prompt = (
        "You are a warm, non-judgmental assistant. In one or two short sentences, in the "
        f"language '{language}', summarize back to the person what you understood for the "
        f"'{section.key}' section, then ask if it is correct. Be encouraging, never judgmental."
    )
    return client.chat(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"[extracted data]\n{extracted.model_dump_json()}"},
        ],
        temperature=0.0,
    )


def interpret_confirmation(client: LlmClient, answer: str, language: str) -> bool:
    """True if the person confirms; False if they correct/deny (fail-safe: False)."""
    try:
        raw = client.chat_json(
            [
                {"role": "system", "content": "Does the person's reply CONFIRM the summary was correct? Reply JSON {\"confirmed\": bool}."},
                {"role": "user", "content": f"[reply, language={language}]\n{answer}"},
            ],
            json_schema=_CONFIRM_SCHEMA,
        )
    except Exception:
        return False
    return raw.get("confirmed") is True
```

File `backend/src/bussola/interview/incongruence.py`:

```python
"""Semantic incongruence detection + gentle clarification (§5, §4)."""

from __future__ import annotations

from bussola.llm.client import LlmClient
from bussola.profile.models import WorkProfile

_SCHEMA = {
    "type": "object",
    "properties": {
        "has_incongruence": {"type": "boolean"},
        "clarification": {"type": "string"},
    },
    "required": ["has_incongruence", "clarification"],
    "additionalProperties": False,
}


def find_incongruence(client: LlmClient, profile: WorkProfile, language: str) -> str | None:
    """Return a gentle clarification question if the profile has a semantic
    incongruence, else None. Fail-safe: None (never block the flow)."""
    prompt = (
        "You check a WORK profile for a SEMANTIC incongruence (e.g. a duration that "
        "doesn't add up, a skill that contradicts the experiences). If found, write a "
        f"gentle, non-judgmental clarification question in the language '{language}'. "
        "Reply JSON {\"has_incongruence\": bool, \"clarification\": string}."
    )
    try:
        raw = client.chat_json(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"[profile]\n{profile.model_dump_json()}"},
            ],
            json_schema=_SCHEMA,
        )
    except Exception:
        return None
    if raw.get("has_incongruence") is True and isinstance(raw.get("clarification"), str):
        return raw["clarification"] or None
    return None
```

- [ ] **Step 4: Eseguire (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_confirm.py backend/tests/interview/test_incongruence.py -q`
Expected: PASS.

- [ ] **Step 5: Committare**

```bash
git add backend/src/bussola/interview/confirm.py backend/src/bussola/interview/incongruence.py backend/tests/interview/test_confirm.py backend/tests/interview/test_incongruence.py
git commit -m "feat(interview): riepilogo & conferma dalla persona + incongruenze semantiche"
```

---

### Task 6: Orchestratore del colloquio (`interview.py`)

**Files:**
- Create: `backend/src/bussola/interview/interview.py`
- Test: `backend/tests/interview/test_interview.py`

**Interfaces:**
- Consumes: `InterviewSession`, `extract_section`, `summarize`/`interpret_confirmation`, `find_incongruence`, `ScopeGuard` (S3), `base_question` (Task 2), `LlmClient`, `LlmUnavailable`, un repository con `create_new() -> str`, `save(profile) -> WorkProfile` e (opzionale) `append_audit`.
- Produces: `Step(kind: str, text: str)` (kind ∈ `question`, `summary`, `clarification`, `refusal`, `unavailable`, `completed`); `Interview(client, scope_guard, repository, *, language="it", audit=None)` con `start() -> Step` e `submit(answer: str) -> Step`.

**Flusso** (deterministico): `start` → `create_new` pseudonimo, prima `question`. Ogni `submit(answer)`:
1. `ScopeGuard.check(answer)`: se rifiutato → `Step("refusal", messaggio)` e **ri-poni la stessa domanda** (non avanza).
2. altrimenti `extract_section` → `session.merge` → `summarize` → `Step("summary", ...)`; il prossimo `submit` è interpretato da `interpret_confirmation`:
   - non confermato → ri-poni la domanda della sezione (`Step("question", ...)`).
   - confermato → `find_incongruence`; se c'è → `Step("clarification", ...)` (il prossimo submit ri-estrae quella sezione); altrimenti **salva** (`repository.save`, `audit`) e **avanza**; se completato → `Step("completed", riepilogo finale)`, altrimenti prossima `question`.
Ogni chiamata LLM è avvolta: su `LlmUnavailable`/errore imprevisto → `Step("unavailable", messaggio)` (mai crash; lo stato non avanza).

- [ ] **Step 1: Scrivere i test (falliscono)**

File `backend/tests/interview/test_interview.py`:

```python
import pytest

from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.llm.client import LlmUnavailable
from bussola.profile.models import WorkProfile


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list[WorkProfile] = []
        self._n = 0

    def create_new(self) -> str:
        self._n += 1
        return f"P-{self._n}"

    def save(self, profile: WorkProfile) -> WorkProfile:
        self.saved.append(profile)
        return profile


ALLOW = '{"allow": true, "category": null, "reason": "ok"}'
REFUSE = '{"allow": false, "category": "out_of_scope", "reason": "off"}'
COMP = {"skills": [{"name": "cooking", "kind": "technical", "evidence": "stated"}], "languages": [], "digital_literacy": None}


def test_start_returns_first_question(make_fake_json_llm):
    client = make_fake_json_llm()
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it")
    step = itw.start()
    assert step.kind == "question"
    assert step.text.strip()


def test_off_topic_answer_is_refused_and_does_not_advance(make_fake_json_llm):
    # scope guard consulted first (text call) -> REFUSE
    client = make_fake_json_llm(text_responses=[REFUSE])
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it")
    itw.start()
    step = itw.submit("che tempo fa domani?")
    assert step.kind == "refusal"


def test_confirmed_section_persists_and_advances(make_fake_json_llm):
    repo = FakeRepo()
    # answer1: guard ALLOW (text), extract COMP (json), summary (text)
    # answer2 (confirm): interpret_confirmation True (json), incongruence none (json) -> save+advance -> next question
    client = make_fake_json_llm(
        json_responses=[COMP, {"confirmed": True}, {"has_incongruence": False, "clarification": ""}],
        text_responses=[ALLOW, "Riepilogo: sai cucinare. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it")
    itw.start()
    s1 = itw.submit("so cucinare")
    assert s1.kind == "summary"
    s2 = itw.submit("sì")
    assert s2.kind == "question"  # advanced to the next section
    assert len(repo.saved) == 1
    assert repo.saved[0].skills[0].name == "cooking"


def test_llm_unavailable_yields_controlled_step(make_fake_json_llm):
    class Boom:
        def chat(self, *a, **k):
            raise LlmUnavailable("down")

        def chat_json(self, *a, **k):
            raise LlmUnavailable("down")

    itw = Interview(Boom(), ScopeGuard(Boom()), FakeRepo(), language="it")
    itw.start()
    step = itw.submit("so cucinare")
    assert step.kind == "unavailable"
```

- [ ] **Step 2: Eseguire (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_interview.py -q`
Expected: FAIL (`interview` inesistente).

- [ ] **Step 3: Implementare**

File `backend/src/bussola/interview/interview.py`:

```python
"""Deterministic interview orchestrator. The app drives the sections; the LLM
formulates, extracts, summarizes and checks incongruences. Degrades gracefully."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bussola.guardrails.refusal import RefusalCategory, refusal_message
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.confirm import interpret_confirmation, summarize
from bussola.interview.extraction import extract_section
from bussola.interview.incongruence import find_incongruence
from bussola.interview.sections import base_question
from bussola.interview.session import InterviewSession
from bussola.llm.client import LlmClient, LlmUnavailable
from bussola.profile.models import WorkProfile


@dataclass(frozen=True)
class Step:
    kind: str  # question | summary | clarification | refusal | unavailable | completed
    text: str


class ProfileStore(Protocol):
    def create_new(self) -> str: ...
    def save(self, profile: WorkProfile) -> WorkProfile: ...


_UNAVAILABLE = {
    "it": "Scusa, ho un problema tecnico momentaneo. Riprova tra poco.",
    "en": "Sorry, I'm having a brief technical problem. Please try again shortly.",
    "fr": "Désolé, j'ai un souci technique momentané. Réessaie dans un instant.",
    "es": "Perdona, tengo un problema técnico momentáneo. Inténtalo de nuevo enseguida.",
    "ar": "عذرًا، لديّ مشكلة تقنية مؤقتة. حاول مرة أخرى بعد قليل.",
}


class Interview:
    def __init__(
        self,
        client: LlmClient,
        scope_guard: ScopeGuard,
        repository: ProfileStore,
        *,
        language: str = "it",
        audit=None,
    ) -> None:
        self._client = client
        self._guard = scope_guard
        self._repo = repository
        self._audit = audit
        self._language = language
        self._session: InterviewSession | None = None
        self._awaiting_confirmation = False

    def _question_step(self) -> Step:
        section = self._session.current_section  # type: ignore[union-attr]
        assert section is not None
        return Step("question", base_question(section, self._language))

    def _unavailable(self) -> Step:
        return Step("unavailable", _UNAVAILABLE.get(self._language, _UNAVAILABLE["en"]))

    def start(self) -> Step:
        pseudonym = self._repo.create_new()
        self._session = InterviewSession(pseudonym, self._language)
        self._awaiting_confirmation = False
        return self._question_step()

    def submit(self, answer: str) -> Step:
        session = self._session
        assert session is not None, "call start() first"
        try:
            return self._submit(session, answer)
        except LlmUnavailable:
            return self._unavailable()
        except Exception:
            return self._unavailable()

    def _submit(self, session: InterviewSession, answer: str) -> Step:
        section = session.current_section
        assert section is not None

        if self._awaiting_confirmation:
            if interpret_confirmation(self._client, answer, self._language):
                clarification = find_incongruence(self._client, session.profile, self._language)
                if clarification is not None:
                    # Re-open the section: the next submit is a fresh answer
                    # (guard -> extract -> summarize) that re-confirms.
                    self._awaiting_confirmation = False
                    return Step("clarification", clarification)
                self._repo.save(session.profile)
                if self._audit is not None:
                    self._audit(action="interview_section_confirmed", target_pseudonym=session.profile.pseudonym_id)
                self._awaiting_confirmation = False
                session.advance()
                if session.completed:
                    return Step("completed", _final_summary(self._language))
                return self._question_step()
            # not confirmed -> re-ask the section question
            self._awaiting_confirmation = False
            return self._question_step()

        # normal answer: guard -> extract -> summarize -> await confirmation
        decision = self._guard.check(answer, self._language)
        if not decision.allow:
            return Step("refusal", refusal_message(decision.category or RefusalCategory.OUT_OF_SCOPE, self._language))
        extracted = extract_section(self._client, section, answer, self._language)
        session.merge(extracted)
        self._awaiting_confirmation = True
        return Step("summary", summarize(self._client, section, extracted, self._language))


def _final_summary(language: str) -> str:
    messages = {
        "it": "Abbiamo finito, grazie! Ho raccolto il tuo profilo lavorativo.",
        "en": "We're done, thank you! I've gathered your work profile.",
        "fr": "C'est terminé, merci ! J'ai rassemblé ton profil professionnel.",
        "es": "Hemos terminado, ¡gracias! He reunido tu perfil laboral.",
        "ar": "لقد انتهينا، شكرًا لك! لقد جمعت ملفك المهني.",
    }
    return messages.get(language, messages["en"])
```

- [ ] **Step 4: Eseguire (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/interview/test_interview.py -q`
Expected: PASS (4 test).

- [ ] **Step 5: Gate unit completo**

Run:
```bash
backend/.venv/bin/pytest backend/tests -q -k "not live and not adversarial"
backend/.venv/bin/ruff check backend/ && backend/.venv/bin/ruff format --check backend/src/bussola/interview backend/tests/interview backend/src/bussola/llm/client.py
backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/src
```
Expected: unit verdi; ruff/format/mypy puliti sui file toccati.

- [ ] **Step 6: Committare**

```bash
git add backend/src/bussola/interview/interview.py backend/tests/interview/test_interview.py
git commit -m "feat(interview): orchestratore deterministico del colloquio con guard, conferma, incongruenze, degrado"
```

---

### Task 7: Integrazione end-to-end con Qwen2.5 reale (`requires_llm` + DB)

**Files:**
- Test: `backend/tests/interview/test_interview_live.py`

**Interfaces:**
- Consumes: `Interview`, `HttpxLlmClient`, `ScopeGuard`, `ProfileRepository` (S2, contro `bussola_test`), `PiiRedactor`.

- [ ] **Step 1: Scrivere il test di integrazione**

File `backend/tests/interview/test_interview_live.py`:

```python
import httpx
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.llm.client import HttpxLlmClient


def _llm_up() -> bool:
    try:
        httpx.get("http://127.0.0.1:8080/health", timeout=3)
        return True
    except Exception:
        return False


requires_llm = pytest.mark.skipif(not _llm_up(), reason="llama-server non attivo")
pytestmark = requires_llm


def _drive(itw: Interview, answer: str):
    """Answer a section, then confirm; return the step after confirmation."""
    step = itw.submit(answer)
    assert step.kind in ("summary", "refusal", "clarification")
    return itw.submit("sì, è corretto")


def test_synthetic_interview_produces_work_only_profile(app_conn):
    # app_conn: fixture from backend/tests/data/conftest.py (bussola_test)
    redactor = PiiRedactor()
    repo = ProfileRepository(app_conn, redactor)
    client = HttpxLlmClient()
    itw = Interview(client, ScopeGuard(client), repo, language="it")

    itw.start()
    _drive(itw, "So cucinare e faccio manutenzione base. Parlo italiano e un po' di inglese.")
    _drive(itw, "Ho fatto il cuoco per due anni in una mensa.")
    _drive(itw, "Mi piacerebbe lavorare nella ristorazione. Vorrei un corso di sicurezza alimentare.")
    _drive(itw, "Disponibilità a tempo pieno.")
    final = _drive(itw, "Preferisco lavorare in squadra.")

    assert final.kind in ("question", "completed", "clarification")
    # The profile was persisted and is work-only by construction (WorkProfile whitelist).
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM profiles.work_profile")
        assert cur.fetchone()[0] >= 1
```

> Nota (prerequisito del test live): la fixture `app_conn` vive in `backend/tests/data/conftest.py`, non visibile da `tests/interview/`. **Spostare** le fixture del DB (`requires_db`, `test_database`, `db`, `owner_conn`/`app_conn`/`auditor_conn`) da `backend/tests/data/conftest.py` a **`backend/tests/conftest.py`** (conftest condiviso a livello di `tests/`), così sono riusabili da entrambe le cartelle. È una miglioria mirata (riuso trasversale), non un refactor allargato; rieseguire i test del data layer per confermare nessuna regressione.

- [ ] **Step 2: Prerequisiti e esecuzione (server + DB su)**

Run (con Postgres e llama-server attivi):
```bash
docker compose up -d db
bash scripts/serve-llm.sh &   # oppure il binario Vulkan; attendere /health
backend/.venv/bin/pytest backend/tests/interview/test_interview_live.py -v
```
Expected: PASS — un colloquio sintetico completo persiste un `WorkProfile` solo-lavorativo. Se un passo non regge, investigare i prompt di sezione/estrazione (non indebolire le asserzioni).

- [ ] **Step 3: Gate completo + commit**

```bash
backend/.venv/bin/pytest backend/tests -q
backend/.venv/bin/ruff check backend/ && backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/src
git add backend/tests/interview/test_interview_live.py
git commit -m "test(interview): colloquio end-to-end con Qwen2.5 reale (requires_llm)"
```

---

## Note di chiusura (scelte di ambito)

- **Frontend/kiosk** (accessibilità, RTL, comando «ferma», voce): S7/S5.
- **Ripresa a metà sezione**: Fase 2 (le sezioni confermate sono persistite).
- **Fixture DB condivise:** se il test live ne ha bisogno, valutare di spostare le fixture di `tests/data/conftest.py` in `backend/tests/conftest.py` (riuso trasversale) — miglioria mirata, non refactor allargato.

## Verifica di copertura (spec → task)

| Requisito (spec/§) | Task |
|---|---|
| Flusso deterministico app-driven (§3.1) | Task 6 |
| Estrazione per-sezione constrained + Pydantic (§3.2) | Task 1, 4 |
| Riepilogo & conferma dalla persona (§3.3) | Task 5, 6 |
| Incongruenze LLM semantiche + chiarimento gentile (§3.4) | Task 5, 6 |
| Guardrail su ogni risposta (§3.5) | Task 6 |
| Stato in-memory + persistenza per-sezione + audit (§3.6) | Task 3, 6 |
| Domande template i18n (§3.7) | Task 2 |
| Degrado elegante (§2 non-obiettivi/§7.1) | Task 6 |
| Test unit LLM finto + integrazione reale (§6) | Task 1-6 (unit), 7 (live) |
| TDD, dati sintetici, codice inglese (§9/§11) | Tutti |
