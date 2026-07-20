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
