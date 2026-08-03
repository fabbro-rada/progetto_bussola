"""Aggregate/anonymous report DTOs (§7.2/§7.3, Fase 2·B).

Every ``dict[str, Count]`` field here is a MARGINAL distribution (never a
fine cross-tab) whose values have already passed through k-anonymity
suppression in ``bussola.report.service`` before reaching this model. For
the ENUMERATED distributions (``completeness_histogram``, ``skill_kinds``,
``skill_evidence``, ``availability``, ``constraints``, ``trends.*``) a small
cell (1..k-1) arrives as the sentinel string ``"<5"`` (via ``suppress``) —
the key set there is a fixed, public vocabulary, so masking only the count
is enough. For the two FREE-TEXT-keyed distributions, ``languages`` and
``matching.top_gaps``, the key itself would identify a rare attribute
(e.g. a one-of-a-kind language), so a count below k causes the whole entry
to be DROPPED (via ``_suppress_and_drop_rare_keys``) rather than shown as
``"<5"``: those two maps therefore only ever contain keys with a raw
``int`` count ``>= k``, never the ``"<5"`` sentinel. The plain
``int``/``float`` fields (``total_profiles``, ``completed_profiles``,
``average_completeness``, ``total_job_requests``,
``runs``/``evaluated``/``compatible``/``compatible_rate``) are global,
non-identifying aggregates and are never suppressed.

Nothing here carries a pseudonym or per-person data (§2/§5): only counts.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# A suppressed small cell (§ anonymity: k=5 small-cell suppression).
Count = int | Literal["<5"]


class Coverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_profiles: int
    completed_profiles: int
    average_completeness: float
    completeness_histogram: dict[str, Count]


class MatchingAgg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: int
    evaluated: int
    compatible: int
    compatible_rate: float
    top_gaps: dict[str, Count]  # free-text-keyed (recommended_training), rare keys dropped


class Trends(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles_by_week: dict[str, Count]
    job_requests_by_week: dict[str, Count]


class Report(BaseModel):
    """The full aggregate/anonymous report (§7.2 «Metriche minime di
    qualità», extended). Mostly marginal distributions over enumerated
    fields; free text (skill names, sectors, roles) is never turned into a
    category here (no taxonomy, §6). The two exceptions are ``languages``
    (keyed by the free-text ``language`` field) and ``matching.top_gaps``
    (keyed by the free-text ``recommended_training``), which is already
    aggregated frequency data (``matching.match_run.gaps``). Because both
    are free-text-keyed, a rare key is dropped rather than suppressed to
    ``"<5"`` — see the module docstring and
    ``bussola.report.service._suppress_and_drop_rare_keys``."""

    model_config = ConfigDict(extra="forbid")

    coverage: Coverage
    languages: dict[
        str, Count
    ]  # "<language> (<level>)" -> count; free-text-keyed, rare keys dropped
    skill_kinds: dict[str, Count]
    skill_evidence: dict[str, Count]
    availability: dict[str, Count]
    constraints: dict[str, Count]
    total_job_requests: int
    matching: MatchingAgg
    trends: Trends
