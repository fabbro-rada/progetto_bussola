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

from bussola.profile.models import WorkProfile

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
        # presidio-anonymizer ships py.typed but leaves AnonymizerEngine.__init__
        # itself untyped, which trips `disallow_untyped_calls` under strict mode.
        self._anonymizer = AnonymizerEngine()  # type: ignore[no-untyped-call]

    def redact(self, text: str, language: str = "it") -> str:
        if not text:
            return text
        results = self._analyzer.analyze(
            text=text, language=language, entities=_ENTITIES
        )
        if not results:
            return text
        # presidio-analyzer and presidio-anonymizer each declare their own
        # (structurally identical) `RecognizerResult` class, so mypy sees two
        # distinct types here even though this is the documented usage.
        return self._anonymizer.anonymize(
            text=text, analyzer_results=results  # type: ignore[arg-type]
        ).text


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
