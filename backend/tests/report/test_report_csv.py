"""CSV serialization of the aggregate/anonymous report (§7.2/§7.3, Fase 2·B).

`report_to_csv` renders the already-suppressed `Report` DTO as a
multi-section CSV. These tests prove the one property that matters here:
a suppressed cell (`"<5"`) is rendered VERBATIM (never expanded, dropped,
or turned back into a number), and no pseudonym leaks into the output.
Actual k=5 suppression is `bussola.report.service.suppress`'s job (see
`tests/report/test_report.py`), not re-tested here.
"""

from __future__ import annotations

from bussola.report.models import Count, Coverage, MatchingAgg, Report, Trends


def _minimal_report(*, languages: dict[str, Count] | None = None) -> Report:
    """A valid `Report` with empty/zero sections except `languages`, which
    the test overrides to exercise section rendering + suppression."""
    return Report(
        coverage=Coverage(
            total_profiles=0,
            completed_profiles=0,
            average_completeness=0.0,
            completeness_histogram={},
        ),
        languages=languages or {},
        skill_kinds={},
        skill_evidence={},
        availability={},
        constraints={},
        total_job_requests=0,
        matching=MatchingAgg(runs=0, evaluated=0, compatible=0, compatible_rate=0.0, top_gaps={}),
        trends=Trends(profiles_by_week={}, job_requests_by_week={}),
    )


def test_report_to_csv_renders_sections_and_keeps_suppression() -> None:
    from bussola.report.csv import report_to_csv

    rep = _minimal_report(languages={"it (fluent)": 6, "ti (basic)": "<5"})
    csv_text = report_to_csv(rep)

    assert "languages,it (fluent),6" in csv_text
    assert "languages,ti (basic),<5" in csv_text  # cella soppressa resa verbatim
    assert "pseudonym" not in csv_text
