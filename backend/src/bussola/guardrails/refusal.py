"""Structured refusals with localized, non-judgmental messages."""

from __future__ import annotations

from enum import Enum

SUPPORTED_LANGUAGES: tuple[str, ...] = ("it", "en", "fr", "es", "ar")


class RefusalCategory(str, Enum):
    OUT_OF_SCOPE = "out_of_scope"
    MANIPULATION = "manipulation"
    INVALID_INPUT = "invalid_input"


# Warm, non-judgmental messages that keep the person on track (§4).
_MESSAGES: dict[str, dict[RefusalCategory, str]] = {
    "it": {
        RefusalCategory.OUT_OF_SCOPE: "Posso aiutarti solo su lavoro, formazione e orientamento. Torniamo al tuo percorso lavorativo?",
        RefusalCategory.MANIPULATION: "Resto sul mio compito: costruire con te il tuo profilo lavorativo. Ripartiamo da lì?",
        RefusalCategory.INVALID_INPUT: "Non ho capito bene. Puoi ripetere con parole tue, parlando del tuo lavoro o della formazione?",
    },
    "en": {
        RefusalCategory.OUT_OF_SCOPE: "I can only help with work, training and guidance. Shall we get back to your work path?",
        RefusalCategory.MANIPULATION: "I'll stay on my task: building your work profile with you. Shall we continue from there?",
        RefusalCategory.INVALID_INPUT: "I didn't quite get that. Could you rephrase, telling me about your work or training?",
    },
    "fr": {
        RefusalCategory.OUT_OF_SCOPE: "Je peux seulement t'aider sur le travail, la formation et l'orientation. On revient à ton parcours ?",
        RefusalCategory.MANIPULATION: "Je reste sur ma tâche : construire ton profil professionnel avec toi. On continue ?",
        RefusalCategory.INVALID_INPUT: "Je n'ai pas bien compris. Peux-tu reformuler, en parlant de ton travail ou de ta formation ?",
    },
    "es": {
        RefusalCategory.OUT_OF_SCOPE: "Solo puedo ayudarte con trabajo, formación y orientación. ¿Volvemos a tu trayectoria laboral?",
        RefusalCategory.MANIPULATION: "Me mantengo en mi tarea: construir tu perfil laboral contigo. ¿Seguimos por ahí?",
        RefusalCategory.INVALID_INPUT: "No te he entendido bien. ¿Puedes decirlo de otra forma, hablando de tu trabajo o formación?",
    },
    "ar": {
        RefusalCategory.OUT_OF_SCOPE: "أستطيع مساعدتك فقط في العمل والتدريب والتوجيه. هل نعود إلى مسارك المهني؟",
        RefusalCategory.MANIPULATION: "سأبقى في مهمتي: بناء ملفك المهني معك. هل نكمل من هناك؟",
        RefusalCategory.INVALID_INPUT: "لم أفهم جيدًا. هل يمكنك إعادة الصياغة، بالحديث عن عملك أو تدريبك؟",
    },
}


def refusal_message(category: RefusalCategory, language: str) -> str:
    """Return a localized, non-judgmental refusal message (fallback: English)."""
    table = _MESSAGES.get(language, _MESSAGES["en"])
    return table[category]
