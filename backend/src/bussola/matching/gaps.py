"""Formative gaps: each unmet requirement becomes a recommended-training item,
citing the person's own desired training when a topic matches (§10)."""

from __future__ import annotations

from bussola.matching.models import GapItem, RequirementVerdict
from bussola.profile.models import WorkProfile


def compute(verdicts: list[RequirementVerdict], profile: WorkProfile) -> list[GapItem]:
    gaps: list[GapItem] = []
    for verdict in verdicts:
        if verdict.satisfied:
            continue
        gaps.append(
            GapItem(
                requirement=verdict.requirement,
                recommended_training=_recommend(verdict.requirement, profile),
            )
        )
    return gaps


def _recommend(requirement: str, profile: WorkProfile) -> str:
    needle = requirement.strip().lower()
    for training in profile.desired_training:
        if needle in training.topic.strip().lower() or training.topic.strip().lower() in needle:
            return training.topic
    return f"formazione in {requirement}"
