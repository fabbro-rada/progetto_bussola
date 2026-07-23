"""Declarative interview sections. The app drives these in fixed order; the LLM
fills each section's extraction model (constrained), never the flow."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from bussola.profile.enums import (
    Availability,
    DigitalLiteracy,
    OperationalNoteCategory,
    WorkConstraint,
)
from bussola.profile.models import DesiredTraining, LanguageKnown, Skill, WorkExperience

_STRICT = ConfigDict(extra="forbid")


class CompetenzeExtraction(BaseModel):
    model_config = _STRICT
    skills: list[Skill] = Field(default_factory=list)
    languages: list[LanguageKnown] = Field(default_factory=list)
    digital_literacy: DigitalLiteracy | None = None


class EsperienzeExtraction(BaseModel):
    model_config = _STRICT
    experiences: list[WorkExperience] = Field(default_factory=list)


class AspirazioniExtraction(BaseModel):
    model_config = _STRICT
    fields_of_interest: list[str] = Field(default_factory=list, max_length=20)
    desired_training: list[DesiredTraining] = Field(default_factory=list)


class VincoliExtraction(BaseModel):
    model_config = _STRICT
    availability: Availability | None = None
    constraints: list[WorkConstraint] = Field(default_factory=list)


class PreferenzeExtraction(BaseModel):
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
        CompetenzeExtraction,
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
        EsperienzeExtraction,
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
        AspirazioniExtraction,
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
        VincoliExtraction,
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
        PreferenzeExtraction,
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
