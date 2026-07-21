"""Output PII filter (defense in depth).

The primary guarantee that a profile holds only work data is structural
(the `WorkProfile` whitelist). This module is the second layer: it detects
and redacts personal data that might slip into free-text fields before they
are stored or shown.

Pattern-based recognizers (email, phone, IBAN, credit card, IP address) are
language-agnostic: they work for every supported language — all five of
`it`, `en`, `fr`, `es`, `ar` (CLAUDE.md §8) — with no NLP model at all. They
only need the language to be *registered* with some spaCy pipeline so that
Presidio can tokenize the text; the pipeline itself can be empty.

Name/location detection (NER) additionally needs a trained language model.
English NER is provided by `en_core_web_lg`, which is MIT-licensed. NER for
Italian, French, Spanish and Arabic is DEFERRED: the readily available
Italian spaCy NER model, for instance, is licensed CC BY-NC-SA 3.0
(NonCommercial + copyleft), which is not a permissive license and cannot be
used here (CLAUDE.md §3); no permissive multilingual NER model has been
adopted yet. Until one is, `it`, `fr`, `es` and `ar` are each registered as a
**blank** spaCy pipeline (`spacy.blank(lang)`): tokenizer only, no downloaded
model data, ships with the MIT-licensed `spacy` library itself. This keeps
pattern-based redaction fully working for all five languages; only
NER-derived entities (PERSON, LOCATION) are unavailable outside English. The
whitelist remains the primary guarantee, so this is acceptable
defense-in-depth degradation, not a security gap — but it does mean a crash
on redaction (`ValueError: No matching recognizers were found`) is not an
acceptable failure mode for any of the five supported languages: every one
of them must be registered.
"""

from __future__ import annotations

import spacy
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from presidio_anonymizer import AnonymizerEngine

from bussola.profile.models import WorkProfile

# CLAUDE.md §8: the five supported languages, full stop. English gets full
# (MIT) NER; the rest get pattern-only (blank pipeline) redaction — see the
# module docstring. Every one of the five MUST be registered: an unhandled
# language would make `redact()` raise instead of degrading gracefully.
_SUPPORTED_LANGUAGES = ["it", "en", "fr", "es", "ar"]
_BLANK_PIPELINE_LANGUAGES = ["it", "fr", "es", "ar"]
_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IBAN_CODE",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "LOCATION",
]


class _MultilingualNlpEngine(SpacyNlpEngine):
    """spaCy engine: full (MIT) NER for English, patterns-only elsewhere.

    `it`, `fr`, `es` and `ar` are loaded as blank pipelines instead of
    downloaded models, so they have no NER component: PERSON/LOCATION
    detection is unavailable for them, but tokenization still works, which
    is all Presidio's pattern recognizers need.
    """

    def load(self) -> None:
        # `SpacyNlpEngine.__init__` sets `self.nlp = None` with no type
        # annotation, so mypy infers the attribute's type as `None` rather
        # than `dict[str, Language] | None` (it only widens from that
        # first assignment, not from `SpacyNlpEngine.load`'s own body,
        # which we are deliberately overriding here). The assignment
        # below is exactly what the base class itself does at runtime.
        self.nlp = {  # type: ignore[assignment]
            "en": spacy.load("en_core_web_lg"),
            **{lang: spacy.blank(lang) for lang in _BLANK_PIPELINE_LANGUAGES},
        }


class PiiRedactor:
    """Redacts personal data from free text.

    Construction loads NLP models and is expensive — build once and reuse.
    """

    def __init__(self) -> None:
        nlp_engine = _MultilingualNlpEngine()
        nlp_engine.load()
        self._analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine, supported_languages=_SUPPORTED_LANGUAGES
        )
        # presidio-anonymizer ships py.typed but leaves AnonymizerEngine.__init__
        # itself untyped, which trips `disallow_untyped_calls` under strict mode.
        self._anonymizer = AnonymizerEngine()  # type: ignore[no-untyped-call]

    def redact(self, text: str, language: str = "it") -> str:
        if not text:
            return text
        results = self._analyzer.analyze(text=text, language=language, entities=_ENTITIES)
        if not results:
            return text
        # presidio-analyzer and presidio-anonymizer each declare their own
        # (structurally identical) `RecognizerResult` class, so mypy sees two
        # distinct types here even though this is the documented usage.
        return self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,  # type: ignore[arg-type]
        ).text


def sanitize_profile(
    profile: WorkProfile, redactor: PiiRedactor, language: str = "it"
) -> WorkProfile:
    """Return a re-validated deep copy of the profile with PII redacted from
    every free-text field. The original profile is left untouched.

    Redaction replaces a detected PII span with a placeholder token (e.g.
    `<EMAIL_ADDRESS>`) that can be longer than the original span, so the
    redacted copy is re-validated through `WorkProfile.model_validate`
    before being returned: the caller can never receive a profile that
    silently violates its own schema.

    Raises:
        pydantic.ValidationError: if redaction expansion pushes a
            free-text field beyond its `max_length` (fail-closed contract:
            an over-length, silently invalid profile is never returned).
            Callers must be prepared to handle this.
    """
    clean = profile.model_copy(deep=True)

    for skill in clean.skills:
        skill.name = redactor.redact(skill.name, language)

    for experience in clean.experiences:
        experience.role = redactor.redact(experience.role, language)
        experience.sector = redactor.redact(experience.sector, language)

    if clean.aspiration is not None:
        clean.aspiration.fields_of_interest = [
            redactor.redact(item, language) for item in clean.aspiration.fields_of_interest
        ]

    for training in clean.desired_training:
        training.topic = redactor.redact(training.topic, language)

    return WorkProfile.model_validate(clean.model_dump())
