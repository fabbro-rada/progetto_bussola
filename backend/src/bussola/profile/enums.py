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
