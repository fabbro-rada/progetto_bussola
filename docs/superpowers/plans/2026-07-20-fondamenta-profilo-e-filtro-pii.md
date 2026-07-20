# Piano 1 — Fondamenta, modello del profilo e filtro PII

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire le fondamenta del backend e il **modello del profilo lavorativo come whitelist** (per costruzione non può contenere reati, salute, dati familiari o valutazioni sulla persona), più il **filtro PII in uscita** come seconda linea di difesa.

**Architecture:** Package Python `bussola` con layout `src/`. Due moduli a responsabilità singola: `profile/` (schema Pydantic rigoroso + enum) e `guardrails/` (redazione PII con Presidio). Nessun LLM, nessun database, nessuna rete: è logica pura, con test deterministici e veloci. È la base strutturale di sicurezza su cui poggiano tutti i piani successivi.

**Tech Stack:** Python 3.12, Pydantic v2 (schema + validazione), Presidio (analyzer + anonymizer) con spaCy (NER it/en), pytest (test). Tutto open source, licenze permissive, nessuna API esterna.

## Global Constraints

Ogni task eredita implicitamente questi vincoli (valori copiati dal nucleo `CLAUDE.md` e da `STATO_TECNICO.md`):

- **Locale / on-premise:** nessuna API esterna, nessun servizio a pagamento, nessun dato verso terzi.
- **Open source permissivo:** solo componenti a licenza aperta (Pydantic MIT, Presidio MIT, spaCy MIT, pytest MIT).
- **Budget nullo:** deve girare sull'hardware già disponibile.
- **Profilo solo-lavoro (whitelist):** il profilo **non** può contenere reati, posizione giuridica, pericolosità, dati sanitari, dati familiari, inferenze o punteggi sulla persona. Deve valere *per costruzione*.
- **Privacy by design:** minimizzazione dei dati; filtro dei dati personali prima di salvare o mostrare.
- **TDD:** test prima del codice (RED → GREEN → REFACTOR).
- **Solo dati sintetici:** mai dati reali di persone nei test.
- **Convenzioni:** documenti in italiano, **codice e identificatori in inglese**, stringhe utente esternalizzate (non pertinente in questo piano: nessuna stringa utente qui).
- **Runtime Python:** 3.12.
- **Cinque lingue del progetto:** it, en, fr, es, ar (in questo piano il NER PII copre it+en; l'estensione a fr/es/ar è prevista in un piano successivo — vedi Note di chiusura).
- **Gate di commit:** ogni commit deve passare `pytest`. Consigliati anche `ruff check` e `mypy` (configurati nel Task 1).

---

## Struttura dei file (dove va cosa)

```
backend/
├── pyproject.toml                         # progetto, dipendenze, config pytest/ruff/mypy
├── src/bussola/
│   ├── __init__.py                        # package marker
│   ├── profile/
│   │   ├── __init__.py
│   │   ├── enums.py                        # tutti gli enum chiusi (livelli, categorie)
│   │   └── models.py                       # LanguageKnown, Skill, WorkExperience,
│   │                                       #   Aspiration, DesiredTraining, WorkProfile
│   └── guardrails/
│       ├── __init__.py
│       └── pii.py                          # PiiRedactor + sanitize_profile
└── tests/
    ├── profile/
    │   ├── test_models.py                  # modelli foglia + rifiuto campi ignoti
    │   └── test_whitelist.py               # garanzia whitelist (test di sicurezza)
    └── guardrails/
        ├── test_pii.py                     # redazione PII deterministica + NER
        └── test_sanitize_profile.py        # redazione applicata al profilo
```

---

### Task 1: Scaffolding del backend

Prepara il package `bussola`, l'ambiente virtuale e pytest. Deliverable: un test di fumo verde.

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/bussola/__init__.py`
- Create: `backend/tests/test_smoke.py`

**Interfaces:**
- Consumes: nulla.
- Produces: package importabile `bussola`; ambiente `backend/.venv`; comando test `pytest` da dentro `backend/`.

- [ ] **Step 1: Scrivere il test di fumo (fallisce: package inesistente)**

File `backend/tests/test_smoke.py`:

```python
def test_package_is_importable():
    import bussola

    assert bussola is not None
```

- [ ] **Step 2: Creare `pyproject.toml`**

File `backend/pyproject.toml`:

```toml
[project]
name = "bussola"
version = "0.1.0"
description = "Work profiling assistant - backend"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.9,<3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8,<9",
    "ruff>=0.6",
    "mypy>=1.11",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 3: Creare il package marker**

File `backend/src/bussola/__init__.py`:

```python
"""Bussola backend — work profiling assistant."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Creare l'ambiente e installare**

Run (da `backend/`):

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: installazione completata senza errori; `pydantic`, `pytest`, `ruff`, `mypy` presenti.

- [ ] **Step 5: Eseguire il test di fumo (deve passare)**

Run (con `.venv` attivo, da `backend/`):

```bash
pytest tests/test_smoke.py -v
```

Expected: PASS `test_package_is_importable`.

- [ ] **Step 6: Aggiungere `.gitignore` e committare**

File `backend/.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
```

Run:

```bash
git add backend/pyproject.toml backend/src/bussola/__init__.py backend/tests/test_smoke.py backend/.gitignore
git commit -m "chore(backend): scaffolding package bussola + pytest"
```

---

### Task 2: Enum e modelli foglia del profilo

Definisce gli **enum chiusi** e i modelli foglia, tutti con `extra="forbid"` (nessun campo ignoto ammesso). Gli enum chiusi sono parte della garanzia whitelist: dove i valori sono predefiniti, il testo libero non è ammesso.

**Files:**
- Create: `backend/src/bussola/profile/__init__.py` (vuoto)
- Create: `backend/src/bussola/profile/enums.py`
- Create: `backend/src/bussola/profile/models.py`
- Test: `backend/tests/profile/test_models.py`

**Interfaces:**
- Consumes: nulla dai task precedenti.
- Produces (usati dal Task 3 e dal Task 5):
  - Enum: `LanguageLevel`, `DigitalLiteracy`, `EvidenceGrade`, `SkillKind`, `Availability`, `WorkConstraint`, `OperationalNoteCategory`.
  - Modelli (tutti `model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)`):
    - `LanguageKnown(language: str, level: LanguageLevel)`
    - `Skill(name: str, kind: SkillKind, evidence: EvidenceGrade)`
    - `WorkExperience(role: str, sector: str, duration_months: int)`
    - `Aspiration(fields_of_interest: list[str], availability: Availability | None, constraints: list[WorkConstraint])`
    - `DesiredTraining(topic: str)`

- [ ] **Step 1: Scrivere i test dei modelli foglia (falliscono: modelli inesistenti)**

File `backend/tests/profile/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from bussola.profile.enums import (
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
)
from bussola.profile.models import (
    Aspiration,
    DesiredTraining,
    LanguageKnown,
    Skill,
    WorkExperience,
)


def test_language_known_valid():
    lk = LanguageKnown(language="arabic", level=LanguageLevel.NATIVE)
    assert lk.level is LanguageLevel.NATIVE


def test_skill_valid():
    s = Skill(name="welding", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
    assert s.name == "welding"


def test_work_experience_rejects_negative_duration():
    with pytest.raises(ValidationError):
        WorkExperience(role="cook", sector="catering", duration_months=-1)


def test_aspiration_defaults_are_empty():
    a = Aspiration()
    assert a.fields_of_interest == []
    assert a.constraints == []
    assert a.availability is None


def test_desired_training_valid():
    t = DesiredTraining(topic="electrical maintenance")
    assert t.topic == "electrical maintenance"


def test_leaf_model_rejects_unknown_field():
    with pytest.raises(ValidationError):
        Skill(
            name="welding",
            kind=SkillKind.TECHNICAL,
            evidence=EvidenceGrade.STATED,
            secret_note="x",
        )
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

Run: `pytest tests/profile/test_models.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bussola.profile'`.

- [ ] **Step 3: Creare gli enum**

File `backend/src/bussola/profile/__init__.py`: (vuoto)

File `backend/src/bussola/profile/enums.py`:

```python
"""Closed enumerations for the work profile.

Where values are a closed set, free text is deliberately not allowed:
this is part of the whitelist guarantee (the profile cannot hold
arbitrary, potentially sensitive, content in these positions).
"""

from enum import Enum


class LanguageLevel(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    FLUENT = "fluent"
    NATIVE = "native"


class DigitalLiteracy(str, Enum):
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class EvidenceGrade(str, Enum):
    """How strongly a skill is supported by what the person recounted."""

    STATED = "stated"  # simply mentioned
    DEMONSTRATED = "demonstrated"  # backed by a concrete experience
    CERTIFIED = "certified"  # backed by a formal qualification


class SkillKind(str, Enum):
    TECHNICAL = "technical"
    SOFT = "soft"


class Availability(str, Enum):
    """Work-scheduling availability only. Deliberately NOT about juridical
    regime (e.g. whether external work is legally permitted): that is a
    red-line topic and has no field here."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    FLEXIBLE = "flexible"


class WorkConstraint(str, Enum):
    """Work-scheduling / training constraints only. Deliberately NOT about
    health or physical limitations: those are sensitive data and have no
    field here."""

    NO_NIGHT_SHIFTS = "no_night_shifts"
    PART_TIME_ONLY = "part_time_only"
    NEEDS_TRAINING_FIRST = "needs_training_first"


class OperationalNoteCategory(str, Enum):
    """Closed set of operational notes. Free text is NOT allowed here."""

    NEEDS_LANGUAGE_SUPPORT = "needs_language_support"
    NEEDS_LITERACY_SUPPORT = "needs_literacy_support"
    LIMITED_AVAILABILITY = "limited_availability"
    PREFERS_TEAM_WORK = "prefers_team_work"
    PREFERS_SOLO_WORK = "prefers_solo_work"
```

- [ ] **Step 4: Creare i modelli foglia**

File `backend/src/bussola/profile/models.py`:

```python
"""Work profile data model (Pydantic v2).

Every model forbids unknown fields (`extra="forbid"`). This is the
structural core of the profile-as-whitelist guarantee.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from bussola.profile.enums import (
    Availability,
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
    WorkConstraint,
)

# Shared strict config: unknown fields are rejected; strings are trimmed.
_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LanguageKnown(BaseModel):
    model_config = _STRICT

    language: str = Field(min_length=2, max_length=32)
    level: LanguageLevel


class Skill(BaseModel):
    model_config = _STRICT

    name: str = Field(min_length=1, max_length=80)
    kind: SkillKind
    evidence: EvidenceGrade


class WorkExperience(BaseModel):
    model_config = _STRICT

    role: str = Field(min_length=1, max_length=80)
    sector: str = Field(min_length=1, max_length=80)
    duration_months: int = Field(ge=0, le=720)  # 0..60 years


class Aspiration(BaseModel):
    model_config = _STRICT

    fields_of_interest: list[str] = Field(default_factory=list, max_length=20)
    availability: Availability | None = None
    constraints: list[WorkConstraint] = Field(default_factory=list)


class DesiredTraining(BaseModel):
    model_config = _STRICT

    topic: str = Field(min_length=1, max_length=80)
```

- [ ] **Step 5: Eseguire i test (devono passare)**

Run: `pytest tests/profile/test_models.py -v`
Expected: PASS (6 test).

- [ ] **Step 6: Committare**

```bash
git add backend/src/bussola/profile/__init__.py backend/src/bussola/profile/enums.py backend/src/bussola/profile/models.py backend/tests/profile/test_models.py
git commit -m "feat(profile): enum chiusi e modelli foglia con extra=forbid"
```

---

### Task 3: `WorkProfile` e garanzia whitelist (test di sicurezza)

Il modello aggregato e i **test di sicurezza più importanti del piano**: il profilo rifiuta ogni campo non lavorativo *per costruzione*.

**Files:**
- Modify: `backend/src/bussola/profile/models.py` (aggiunge `WorkProfile` + import)
- Test: `backend/tests/profile/test_whitelist.py`

**Interfaces:**
- Consumes: modelli foglia ed enum del Task 2.
- Produces (usato da Task 5 e piani successivi):
  - `WorkProfile(pseudonym_id: str, languages: list[LanguageKnown], digital_literacy: DigitalLiteracy | None, skills: list[Skill], experiences: list[WorkExperience], aspiration: Aspiration | None, desired_training: list[DesiredTraining], operational_notes: list[OperationalNoteCategory])`, con `model_config = ConfigDict(extra="forbid", ...)`.

- [ ] **Step 1: Scrivere i test della whitelist (falliscono: `WorkProfile` inesistente)**

File `backend/tests/profile/test_whitelist.py`:

```python
import pytest
from pydantic import ValidationError

from bussola.profile.enums import (
    DigitalLiteracy,
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
)
from bussola.profile.models import LanguageKnown, Skill, WorkProfile


def test_minimal_profile_is_valid():
    p = WorkProfile(pseudonym_id="P-001")
    assert p.pseudonym_id == "P-001"
    assert p.skills == []
    assert p.operational_notes == []


def test_rich_profile_round_trips():
    p = WorkProfile(
        pseudonym_id="P-002",
        languages=[LanguageKnown(language="italian", level=LanguageLevel.FLUENT)],
        digital_literacy=DigitalLiteracy.BASIC,
        skills=[
            Skill(name="cooking", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
        ],
    )
    restored = WorkProfile.model_validate(p.model_dump())
    assert restored == p


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "criminal_record",
        "reato",
        "offense",
        "sentence",
        "juridical_position",
        "health",
        "diagnosis",
        "medical_notes",
        "family",
        "family_situation",
        "risk_score",
        "dangerousness",
        "recidivism_risk",
    ],
)
def test_forbidden_fields_are_rejected(forbidden_field):
    with pytest.raises(ValidationError):
        WorkProfile(pseudonym_id="P-003", **{forbidden_field: "whatever"})


def test_operational_notes_reject_free_text():
    # Only predefined categories are allowed; free text must be rejected.
    with pytest.raises(ValidationError):
        WorkProfile(pseudonym_id="P-004", operational_notes=["condannato per furto"])
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

Run: `pytest tests/profile/test_whitelist.py -v`
Expected: FAIL con `ImportError: cannot import name 'WorkProfile'`.

- [ ] **Step 3: Aggiungere `WorkProfile` a `models.py`**

Nel file `backend/src/bussola/profile/models.py`, estendere l'import degli enum e aggiungere il modello in coda.

Sostituire il blocco di import degli enum con:

```python
from bussola.profile.enums import (
    Availability,
    DigitalLiteracy,
    EvidenceGrade,
    LanguageLevel,
    OperationalNoteCategory,
    SkillKind,
    WorkConstraint,
)
```

Aggiungere in fondo al file:

```python
class WorkProfile(BaseModel):
    """Work-only profile.

    By construction it cannot hold crimes, juridical position, health,
    family data, or any judgement/score about the person: there is simply
    no field for them, and unknown fields are rejected (`extra="forbid"`).
    """

    model_config = _STRICT

    pseudonym_id: str = Field(min_length=1, max_length=64)
    languages: list[LanguageKnown] = Field(default_factory=list)
    digital_literacy: DigitalLiteracy | None = None
    skills: list[Skill] = Field(default_factory=list)
    experiences: list[WorkExperience] = Field(default_factory=list)
    aspiration: Aspiration | None = None
    desired_training: list[DesiredTraining] = Field(default_factory=list)
    operational_notes: list[OperationalNoteCategory] = Field(default_factory=list)
```

- [ ] **Step 4: Eseguire i test (devono passare)**

Run: `pytest tests/profile/test_whitelist.py -v`
Expected: PASS (tutti, inclusi i 13 casi parametrizzati di `test_forbidden_fields_are_rejected`).

- [ ] **Step 5: Eseguire l'intera suite del profilo**

Run: `pytest tests/profile/ -v`
Expected: PASS (Task 2 + Task 3).

- [ ] **Step 6: Committare**

```bash
git add backend/src/bussola/profile/models.py backend/tests/profile/test_whitelist.py
git commit -m "feat(profile): WorkProfile con garanzia whitelist e test di sicurezza"
```

---

### Task 4: `PiiRedactor` — filtro PII in uscita

Seconda linea di difesa (§7.3): rileva e reda dati personali nel testo libero. La garanzia *primaria* resta la whitelist (Task 3); questo è il livello di ridondanza.

**Files:**
- Modify: `backend/pyproject.toml` (aggiunge dipendenze Presidio + spaCy)
- Create: `backend/src/bussola/guardrails/__init__.py` (vuoto)
- Create: `backend/src/bussola/guardrails/pii.py` (solo `PiiRedactor` in questo task)
- Test: `backend/tests/guardrails/test_pii.py`

**Interfaces:**
- Consumes: nulla dai task del profilo.
- Produces (usato dal Task 5):
  - `PiiRedactor()` — costruzione costosa (carica modelli NLP), da riusare.
  - `PiiRedactor.redact(text: str, language: str = "it") -> str` — ritorna il testo con le entità personali sostituite da segnaposto `<ENTITY_TYPE>` (es. `<PERSON>`, `<EMAIL_ADDRESS>`).

- [ ] **Step 1: Aggiungere le dipendenze e installarle**

Nel file `backend/pyproject.toml`, sostituire la sezione `dependencies` con:

```toml
dependencies = [
    "pydantic>=2.9,<3",
    "presidio-analyzer>=2.2,<3",
    "presidio-anonymizer>=2.2,<3",
    "spacy>=3.7,<4",
]
```

Run (con `.venv` attivo, da `backend/`):

```bash
pip install -e ".[dev]"
python -m spacy download it_core_news_lg
python -m spacy download en_core_web_lg
```

Expected: installazione ok; i due modelli spaCy scaricati (~500 MB ciascuno; il disco è abbondante).

- [ ] **Step 2: Scrivere i test del redattore (falliscono: modulo inesistente)**

File `backend/tests/guardrails/test_pii.py`:

```python
import pytest

from bussola.guardrails.pii import PiiRedactor


@pytest.fixture(scope="session")
def redactor() -> PiiRedactor:
    # Expensive to build (loads NLP models); build once for the session.
    return PiiRedactor()


def test_redacts_email(redactor):
    out = redactor.redact("scrivimi a mario.rossi@example.com per info", language="it")
    assert "mario.rossi@example.com" not in out
    assert "<EMAIL_ADDRESS>" in out


def test_redacts_phone_number(redactor):
    out = redactor.redact("il mio numero e' +39 333 123 4567", language="it")
    assert "333 123 4567" not in out


def test_redacts_person_name_italian(redactor):
    out = redactor.redact("ho lavorato con Marco Rossi in cucina", language="it")
    assert "Marco Rossi" not in out


def test_text_without_pii_is_unchanged(redactor):
    text = "esperienza in saldatura e carpenteria metallica"
    assert redactor.redact(text, language="it") == text


def test_empty_text_is_returned_as_is(redactor):
    assert redactor.redact("", language="it") == ""
```

- [ ] **Step 3: Eseguire i test (devono fallire)**

Run: `pytest tests/guardrails/test_pii.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bussola.guardrails'`.

- [ ] **Step 4: Implementare `PiiRedactor`**

File `backend/src/bussola/guardrails/__init__.py`: (vuoto)

File `backend/src/bussola/guardrails/pii.py`:

```python
"""Output PII filter (defense in depth).

The primary guarantee that a profile holds only work data is structural
(the `WorkProfile` whitelist). This module is the second layer: it detects
and redacts personal data that might slip into free-text fields before they
are stored or shown.

Pattern-based recognizers (email, phone, IBAN, ...) are language-agnostic.
Name/location detection uses spaCy NER; here it is configured for it + en.
Adding fr/es/ar is a later, i18n-focused step.
"""

from __future__ import annotations

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

_NLP_CONFIGURATION = {
    "nlp_engine_name": "spacy",
    "models": [
        {"lang_code": "it", "model_name": "it_core_news_lg"},
        {"lang_code": "en", "model_name": "en_core_web_lg"},
    ],
}
_SUPPORTED_LANGUAGES = ["it", "en"]
_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IBAN_CODE",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "LOCATION",
]


class PiiRedactor:
    """Redacts personal data from free text.

    Construction loads NLP models and is expensive — build once and reuse.
    """

    def __init__(self) -> None:
        nlp_engine = NlpEngineProvider(
            nlp_configuration=_NLP_CONFIGURATION
        ).create_engine()
        self._analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine, supported_languages=_SUPPORTED_LANGUAGES
        )
        self._anonymizer = AnonymizerEngine()

    def redact(self, text: str, language: str = "it") -> str:
        if not text:
            return text
        results = self._analyzer.analyze(
            text=text, language=language, entities=_ENTITIES
        )
        if not results:
            return text
        return self._anonymizer.anonymize(text=text, analyzer_results=results).text
```

- [ ] **Step 5: Eseguire i test (devono passare)**

Run: `pytest tests/guardrails/test_pii.py -v`
Expected: PASS (5 test). *Nota:* il primo caricamento dei modelli rende la sessione più lenta; è normale.

- [ ] **Step 6: Committare**

```bash
git add backend/pyproject.toml backend/src/bussola/guardrails/__init__.py backend/src/bussola/guardrails/pii.py backend/tests/guardrails/test_pii.py
git commit -m "feat(guardrails): PiiRedactor per il filtro PII in uscita"
```

---

### Task 5: `sanitize_profile` — redazione applicata al profilo

Applica il redattore PII a **tutti i campi a testo libero** del profilo, senza mutare l'originale.

**Files:**
- Modify: `backend/src/bussola/guardrails/pii.py` (aggiunge `sanitize_profile` + import)
- Test: `backend/tests/guardrails/test_sanitize_profile.py`

**Interfaces:**
- Consumes: `WorkProfile` (Task 3), `PiiRedactor` (Task 4).
- Produces (usato dai piani successivi, prima di salvare/mostrare):
  - `sanitize_profile(profile: WorkProfile, redactor: PiiRedactor, language: str = "it") -> WorkProfile` — ritorna una copia profonda con i campi liberi redatti (`skill.name`, `experience.role`, `experience.sector`, `aspiration.fields_of_interest[]`, `desired_training[].topic`). L'originale resta invariato.

- [ ] **Step 1: Scrivere i test (falliscono: funzione inesistente)**

File `backend/tests/guardrails/test_sanitize_profile.py`:

```python
import pytest

from bussola.guardrails.pii import PiiRedactor, sanitize_profile
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkExperience, WorkProfile


@pytest.fixture(scope="session")
def redactor() -> PiiRedactor:
    return PiiRedactor()


def test_sanitize_redacts_pii_in_free_text(redactor):
    profile = WorkProfile(
        pseudonym_id="P-010",
        skills=[
            Skill(
                name="assistente di Marco Rossi",
                kind=SkillKind.SOFT,
                evidence=EvidenceGrade.STATED,
            )
        ],
        experiences=[
            WorkExperience(role="aiuto cuoco", sector="ristorazione", duration_months=12)
        ],
    )
    clean = sanitize_profile(profile, redactor, language="it")

    assert "Marco Rossi" not in clean.skills[0].name
    # Non-free-text data is preserved unchanged.
    assert clean.experiences[0].duration_months == 12
    assert clean.pseudonym_id == "P-010"


def test_sanitize_does_not_mutate_original(redactor):
    profile = WorkProfile(
        pseudonym_id="P-011",
        skills=[
            Skill(
                name="contatto mario@example.com",
                kind=SkillKind.SOFT,
                evidence=EvidenceGrade.STATED,
            )
        ],
    )
    sanitize_profile(profile, redactor, language="it")

    # The original object is untouched.
    assert profile.skills[0].name == "contatto mario@example.com"
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

Run: `pytest tests/guardrails/test_sanitize_profile.py -v`
Expected: FAIL con `ImportError: cannot import name 'sanitize_profile'`.

- [ ] **Step 3: Aggiungere `sanitize_profile` a `pii.py`**

In cima a `backend/src/bussola/guardrails/pii.py`, aggiungere l'import:

```python
from bussola.profile.models import WorkProfile
```

In fondo allo stesso file, aggiungere la funzione:

```python
def sanitize_profile(
    profile: WorkProfile, redactor: PiiRedactor, language: str = "it"
) -> WorkProfile:
    """Return a deep copy of the profile with PII redacted from every
    free-text field. The original profile is left untouched."""
    clean = profile.model_copy(deep=True)

    for skill in clean.skills:
        skill.name = redactor.redact(skill.name, language)

    for experience in clean.experiences:
        experience.role = redactor.redact(experience.role, language)
        experience.sector = redactor.redact(experience.sector, language)

    if clean.aspiration is not None:
        clean.aspiration.fields_of_interest = [
            redactor.redact(item, language)
            for item in clean.aspiration.fields_of_interest
        ]

    for training in clean.desired_training:
        training.topic = redactor.redact(training.topic, language)

    return clean
```

- [ ] **Step 4: Eseguire i test (devono passare)**

Run: `pytest tests/guardrails/test_sanitize_profile.py -v`
Expected: PASS (2 test).

- [ ] **Step 5: Eseguire l'intera suite + qualità**

Run (da `backend/`):

```bash
pytest -v
ruff check .
mypy src
```

Expected: `pytest` tutto verde; `ruff` senza errori; `mypy` senza errori (o solo su dipendenze esterne — in tal caso aggiungere `ignore_missing_imports` mirato).

- [ ] **Step 6: Committare**

```bash
git add backend/src/bussola/guardrails/pii.py backend/tests/guardrails/test_sanitize_profile.py
git commit -m "feat(guardrails): sanitize_profile applica il filtro PII al profilo"
```

---

## Note di chiusura (scelte di ambito, non segnaposto)

- **NER PII solo it+en in questo piano.** I riconoscitori a pattern (email, telefono, IBAN, carta) sono già indipendenti dalla lingua. L'estensione del NER a fr/es (modelli spaCy disponibili) e ad ar (supporto spaCy limitato: si valuterà un riconoscitore alternativo, con i pattern comunque attivi) è materiale del piano di **i18n/frontend** (Piano 7) o di un mini-piano dedicato. Deciso così per tenere questo piano deterministico e veloce.
- **Filtro semantico dei temi vietati** (reati/salute *dentro* il testo libero) non è qui: richiede il modello ed è collocato nei **guardrail comportamentali** (Piano 3) e nell'**estrazione** (Piano 4). Qui la difesa è strutturale (whitelist) + PII.
- **Persistenza** del profilo: Piano 2 (PostgreSQL, segregazione, audit, cifratura).

## Verifica di copertura (spec → task)

| Requisito (nucleo/tecnico) | Task |
|---|---|
| Profilo solo-lavoro *per costruzione* (§2, §5, §7.3) | Task 2, 3 |
| Nessun campo per reati/salute/famiglia/punteggi | Task 3 (test parametrizzati) |
| Note operative solo per categorie predefinite (§5) | Task 2 (enum), Task 3 (test) |
| Estrazione conforme a schema definito (§7.3) | Task 2, 3 (schema Pydantic) |
| Filtro dei dati personali in uscita (§7.3) | Task 4, 5 |
| TDD, solo dati sintetici (§9) | Tutti i task |
| Open source, locale, budget zero (§3) | Task 1 (dipendenze) |
| Codice in inglese (§11) | Tutti i task |
