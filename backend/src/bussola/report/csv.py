"""CSV serialization of the aggregate/anonymous report (§7.2/§7.3, Fase 2·B).

`report_to_csv` renders a `Report` (already k=5-suppressed by
`bussola.report.service.compute_report`) as a multi-section CSV: one row
per leaf value as ``section,key,value``. This module does no suppression
of its own — a cell that arrives as the sentinel string ``"<5"`` is
written out verbatim, never expanded back into a number and never
dropped. The JSON form of the report is simply ``report.model_dump()``;
no equivalent function is needed for JSON.

Section order and, within a dict-valued section, key order are both
fixed (declaration order for sections, alphabetical for dict keys) so the
output is deterministic across calls and stable for tests.
"""

from __future__ import annotations

import csv
import io

from bussola.report.models import Count, Report

_HEADER = ("section", "key", "value")

# A CSV cell value: either a plain aggregate (int/float, never suppressed)
# or a per-key distribution count (already possibly suppressed to "<5").
_Value = Count | float

_Row = tuple[str, str, _Value]


def _dict_rows(section: str, values: dict[str, Count]) -> list[_Row]:
    """One row per key of a `dict[str, Count]` section, in alphabetical
    key order (independent of the dict's insertion order) so the CSV is
    deterministic no matter how `values` was built upstream."""
    return [(section, key, values[key]) for key in sorted(values)]


def report_to_csv(report: Report) -> str:
    """Render `report` as a multi-section CSV (`section,key,value` rows).

    Suppressed cells (the sentinel `"<5"`) render verbatim — this function
    never re-implements or bypasses suppression (§ anonymity); it only
    serializes what `compute_report` already produced.
    """
    rows: list[_Row] = [
        ("coverage", "total_profiles", report.coverage.total_profiles),
        ("coverage", "completed_profiles", report.coverage.completed_profiles),
        ("coverage", "average_completeness", report.coverage.average_completeness),
        *_dict_rows("completeness_histogram", report.coverage.completeness_histogram),
        *_dict_rows("languages", report.languages),
        *_dict_rows("skill_kinds", report.skill_kinds),
        *_dict_rows("skill_evidence", report.skill_evidence),
        *_dict_rows("availability", report.availability),
        *_dict_rows("constraints", report.constraints),
        ("report", "total_job_requests", report.total_job_requests),
        ("matching", "runs", report.matching.runs),
        ("matching", "evaluated", report.matching.evaluated),
        ("matching", "compatible", report.matching.compatible),
        ("matching", "compatible_rate", report.matching.compatible_rate),
        *_dict_rows("top_gaps", report.matching.top_gaps),
        *_dict_rows("profiles_by_week", report.trends.profiles_by_week),
        *_dict_rows("job_requests_by_week", report.trends.job_requests_by_week),
    ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_HEADER)
    writer.writerows(rows)
    return buffer.getvalue()
