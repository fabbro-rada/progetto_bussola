"""LLM semantic judgment, grounded and structured. For each job requirement the
model answers satisfied/unsatisfied and MUST cite evidence from the profile (or
null). It judges ONLY work fitness against the explicit requirements — never the
person. Fail-safe: an unparseable/invalid answer yields all-unsatisfied verdicts
(no invented data)."""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from bussola.llm.client import LlmClient
from bussola.matching.models import JobRequest, RequirementVerdict
from bussola.profile.models import WorkProfile

_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "satisfied": {"type": "boolean"},
                    "evidence": {"type": ["string", "null"]},
                },
                "required": ["requirement", "satisfied", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

_PROMPT = (
    "You match a WORK profile against a job's requirements. For EACH requirement, "
    "decide if the profile satisfies it and CITE the exact profile element that is "
    "your evidence (a skill name, a role/sector, a training) — or null if not "
    "satisfied. Judge ONLY work fitness against the listed requirements; never judge "
    "the person, never infer anything beyond the profile. Do not invent evidence. "
    'Reply JSON {"verdicts":[{"requirement":string,"satisfied":bool,"evidence":string|null}]} '
    "with exactly one entry per requirement, in the given order."
)


class _Verdicts(BaseModel):
    verdicts: list[RequirementVerdict]


def _requirements(job: JobRequest) -> list[str]:
    return [*job.required_skills, *job.training_prerequisites]


def judge_requirements(
    client: LlmClient, profile: WorkProfile, job: JobRequest, language: str
) -> list[RequirementVerdict]:
    requirements = _requirements(job)
    if not requirements:
        return []
    user = (
        f"[language={language}]\n"
        f"[requirements]\n{json.dumps(requirements, ensure_ascii=False)}\n"
        f"[profile]\n{profile.model_dump_json()}"
    )
    raw = client.chat_json(
        [{"role": "system", "content": _PROMPT}, {"role": "user", "content": user}],
        json_schema=_SCHEMA,
    )
    try:
        parsed = _Verdicts.model_validate(raw)
    except ValidationError:
        return [
            RequirementVerdict(requirement=r, satisfied=False, evidence=None) for r in requirements
        ]
    by_name = {v.requirement: v for v in parsed.verdicts}
    # Re-key to the requested requirements: an unmatched/missing one is unsatisfied.
    return [
        by_name.get(r, RequirementVerdict(requirement=r, satisfied=False, evidence=None))
        for r in requirements
    ]
