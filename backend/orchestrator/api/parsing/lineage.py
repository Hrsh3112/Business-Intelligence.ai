"""Source manifest — where each submitted metric came from, at what grain,
and how fresh it is (Stage 4; critique P0 #2, P2 #9; problem statement Req 2).

This exists because of an asymmetry: the frontend only ever receives the
EnrichedReport, so it can see nothing about the CompanyInput that produced it
— not the grain, not the period coverage, not how much of a series C2 had to
interpolate. All of that is sitting in C2's hands and was simply never sent.

Everything here is derived from data already in the CompanyInput, with one
exception: `source_system` is a label the user declares (or the filename we
were handed). `source_basis` records which of the two it was, so a declared
label is never mistaken for something the system verified. We do not infer a
"CRM system" from a metric name, and we do not date-stamp data we did not see.
"""

from typing import Optional

from api.config.loader import metrics as load_metrics
from api.models.internal import FormMetadata, MetricSource
from api.models.shared import CompanyInput


def _sorted_periods(periods: list[str]) -> list[str]:
    """Period strings sort lexicographically within a single granularity —
    "2024-01" < "2024-02", "2024-Q1" < "2024-Q2", "2023" < "2024" — and a
    metric's periods are single-granularity by the time they reach here
    (validation rejects mixed grain per metric). Anything unexpected sorts
    harmlessly rather than raising."""
    return sorted(periods)


def build_source_manifest(
    company_input: Optional[CompanyInput],
    form_metadata: Optional[FormMetadata] = None,
    upload_filename: Optional[str] = None,
) -> list[MetricSource]:
    """One entry per metric that survived validation and was actually sent.

    Metrics excluded during parsing are deliberately absent: the manifest
    describes what was analysed, and the reasons for exclusions already travel
    in ApiResponse.warnings.
    """
    if company_input is None or not company_input.metrics:
        return []

    catalog = load_metrics()
    declared_default = form_metadata.source_system if form_metadata else None
    per_metric = (form_metadata.metric_sources if form_metadata else None) or {}

    manifest: list[MetricSource] = []
    for entry in company_input.metrics:
        # Precedence: an explicit per-metric declaration, then the submission's
        # declared source, then the filename we were actually given. Each step
        # is weaker evidence than the last, which is what source_basis records.
        if entry.metric_id in per_metric:
            source, basis = per_metric[entry.metric_id], "declared"
        elif declared_default:
            source, basis = declared_default, "declared"
        elif upload_filename:
            source, basis = upload_filename, "upload_filename"
        else:
            source, basis = None, "unknown"

        periods = _sorted_periods([point.period for point in entry.values])

        manifest.append(
            MetricSource(
                metric_id=entry.metric_id,
                display_name=catalog.get(entry.metric_id, {}).get("display_name"),
                source_system=source,
                source_basis=basis,
                grain=entry.granularity.value,
                as_of_period=periods[-1] if periods else None,
                first_period=periods[0] if periods else None,
                points=len(entry.values),
                interpolated_points=sum(1 for point in entry.values if point.interpolated),
                confidence=entry.confidence,
            )
        )

    return manifest
