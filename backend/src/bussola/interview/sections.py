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
        "skills",
        SkillsExtraction,
        {
            "it": "Raccontami cosa sai fare. Vanno bene anche cose imparate fuori da un lavoro. E quali lingue parli?",
            "en": "Tell me what you can do. Things you learned outside of a job count too. And which languages do you speak?",
            "fr": "Raconte-moi ce que tu sais faire. Les choses apprises en dehors d'un emploi comptent aussi. Et quelles langues parles-tu ?",
            "es": "Cuéntame qué sabes hacer. También valen las cosas que aprendiste fuera de un trabajo. ¿Y qué idiomas hablas?",
            "ar": "احكِ لي عمّا تعرف أن تفعله. حتى ما تعلّمته خارج العمل مهمّ. وما اللغات التي تتحدّثها؟",
        },
        "Extract the person's skills (technical/soft, with an evidence grade), known languages with level, and digital literacy, from their reply. Only what they actually said. For each skill NAME keep the person's own everyday words; do NOT translate them into a technical or specialised term (e.g. keep 'falegname', do not rewrite it as 'carpenteria').",
    ),
    Section(
        "experiences",
        ExperiencesExtraction,
        {
            "it": "Che lavori hai fatto finora? Anche brevi o occasionali. Per ognuno dimmi cosa facevi e per quanto tempo.",
            "en": "What jobs have you done so far? Short or occasional ones count too. For each, tell me what you did and for how long.",
            "fr": "Quels travaux as-tu faits jusqu'ici ? Même courts ou occasionnels. Pour chacun, dis-moi ce que tu faisais et pendant combien de temps.",
            "es": "¿Qué trabajos has hecho hasta ahora? También los cortos u ocasionales. Para cada uno, dime qué hacías y durante cuánto tiempo.",
            "ar": "ما الأعمال التي قمت بها حتى الآن؟ حتى القصيرة أو المؤقّتة منها. لكلّ عمل، أخبرني بما كنت تفعله وكم من الوقت.",
        },
        "Extract past work experiences (role, sector, duration in months) from their reply. Only what they actually said. Keep the person's own everyday words for the role; do NOT translate them into a technical or specialised term.",
    ),
    Section(
        "aspirations",
        AspirationsExtraction,
        {
            "it": "Che lavoro ti piacerebbe fare? C'è un corso di formazione che vorresti fare per imparare cose nuove?",
            "en": "What work would you like to do? Is there a training course you'd like to take to learn new things?",
            "fr": "Quel travail aimerais-tu faire ? Y a-t-il une formation que tu voudrais suivre pour apprendre de nouvelles choses ?",
            "es": "¿Qué trabajo te gustaría hacer? ¿Hay algún curso de formación que quisieras hacer para aprender cosas nuevas?",
            "ar": "ما العمل الذي تودّ القيام به؟ هل هناك دورة تدريبية ترغب في حضورها لتتعلّم أشياء جديدة؟",
        },
        "Extract fields of interest and desired training topics from their reply. Only what they actually said.",
    ),
    Section(
        "constraints",
        ConstraintsExtraction,
        {
            "it": "Quanto tempo puoi dedicare al lavoro: tutto il giorno, mezza giornata, o quando serve? Ci sono orari o turni che non puoi fare?",
            "en": "How much time can you give to work: all day, half a day, or when needed? Are there hours or shifts you can't do?",
            "fr": "Combien de temps peux-tu consacrer au travail : toute la journée, une demi-journée, ou selon les besoins ? Y a-t-il des horaires que tu ne peux pas faire, par exemple tôt le matin ou la nuit ?",
            "es": "¿Cuánto tiempo puedes dedicar al trabajo: todo el día, media jornada, o cuando haga falta? ¿Hay horarios o turnos que no puedas hacer?",
            "ar": "كم من الوقت يمكنك تخصيصه للعمل: طوال اليوم، أم نصف يوم، أم عند الحاجة؟ وهل هناك أوقات أو مناوبات لا يمكنك العمل فيها؟",
        },
        "Extract availability (full_time/part_time/flexible) and work-scheduling constraints from their reply. Never health or juridical items. Only what they actually said.",
    ),
    Section(
        "preferences",
        PreferencesExtraction,
        {
            "it": "Un'ultima cosa: ti trovi meglio a lavorare in gruppo o da solo? C'è qualcosa che ti aiuterebbe all'inizio, ad esempio un aiuto con la lingua?",
            "en": "One last thing: do you feel more comfortable working in a group or on your own? Is there something that would help you at the start, for example help with the language?",
            "fr": "Une dernière chose : es-tu plus à l'aise en groupe ou seul ? Y a-t-il quelque chose qui t'aiderait au début, par exemple une aide avec la langue ?",
            "es": "Una última cosa: ¿te sientes mejor trabajando en grupo o solo? ¿Hay algo que te ayudaría al principio, por ejemplo ayuda con el idioma?",
            "ar": "أمر أخير: هل تشعر براحة أكبر في العمل ضمن مجموعة أم بمفردك؟ هل هناك ما قد يساعدك في البداية، مثل مساعدة في اللغة؟",
        },
        "Extract operational notes ONLY from the closed set (needs_language_support, needs_literacy_support, limited_availability, prefers_team_work, prefers_solo_work) from their reply.",
    ),
)


def base_question(section: Section, language: str) -> str:
    """Return the section's base question in `language` (fallback: English)."""
    return section.base_question.get(language, section.base_question["en"])
