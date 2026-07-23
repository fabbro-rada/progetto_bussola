"""Transparent scoring: the fraction of the job's requirements the profile
satisfies. The score is nothing more than the visible verdicts summarized."""

from __future__ import annotations

from bussola.matching.models import RequirementVerdict


def score(verdicts: list[RequirementVerdict]) -> float:
    if not verdicts:
        return 0.0
    satisfied = sum(1 for v in verdicts if v.satisfied)
    return satisfied / len(verdicts)
