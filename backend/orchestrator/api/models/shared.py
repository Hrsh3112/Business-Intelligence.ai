"""Shared schema — the three cross-component contracts.

Canonical source: pipeline-Contract-V1.md (overrides C2-MasterPlan.md §5 wherever
they disagree). C1's repo (`ml_engine/models/`) is canonical over both once repo
access lands (O10) — re-sync this file and update the decision log if it drifts.

    CompanyInput   — produced by C2, consumed by C1. Schema owned by C1.
    AnomalyReport  — produced by C1, consumed by C2 + C3. Schema owned by C1.
    EnrichedReport — produced by C3, consumed by C2. PROPOSED, C3 has not signed off (§11).
"""

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums (Contract §4.1, §5.1)
# ---------------------------------------------------------------------------


class SectorId(str, Enum):
    TECH_SAAS = "TECH_SAAS"
    RETAIL = "RETAIL"
    # MFG is OUT OF SCOPE for MVP (Contract §10)


class RevenueBand(str, Enum):
    UNDER_1M = "<1M"
    ONE_TO_10M = "1M-10M"
    TEN_TO_100M = "10M-100M"
    OVER_100M = ">100M"


class Granularity(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SeverityLabel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    SEVERE = "SEVERE"


class DeviationDirection(str, Enum):
    ABOVE_EXPECTED = "above_expected"
    BELOW_EXPECTED = "below_expected"
    # UNVERIFIED — confirm against C1 repo. Semantics open (Contract O13): a
    # HealthyHighlight has no deviation block, so this can only appear on an
    # Anomaly — but an anomaly deviated by definition. Do not build UI logic
    # that assumes this value is unreachable.
    AS_EXPECTED = "as_expected"


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DETERIORATING = "deteriorating"


class RefusalReason(str, Enum):
    NO_METRICS_SUBMITTED = "no_metrics_submitted"
    LOW_DATA_CONFIDENCE = "low_data_confidence"
    INSUFFICIENT_PERIODS = "insufficient_periods"
    # Reserved, never triggered by any current code path (Contract §5.3).
    # Do NOT write a two-branch switch on this enum — handle all four values
    # or use a default branch, so nothing breaks when this trigger lands.
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"


class Persona(str, Enum):
    """Who the report is being produced for.

    ⚠️ C2-PROPOSED ADDITION TO THE SHARED SCHEMA — NOT SIGNED OFF.
    The only field C2 has added to this file. Recorded in full because the
    next person to read it needs the whole story.

    WHY IT IS HERE. The problem statement requires at least two personas
    receiving different narratives. The narrative is C3's, generated from an
    AnomalyReport. For a persona to influence that prose it must reach the C3
    call, and the only route that does not breach C2's architectural boundary
    (`run_pipeline()` takes a CompanyInput and nothing else) is to carry it
    inside the CompanyInput. Hence a field on the shared contract.

    WHY IT IS SAFE FOR C1. `ml_engine.models.input_schema.CompanyInput`
    declares no `model_config`, so Pydantic v2's default `extra="ignore"`
    applies: `orchestration/c1_adapter.py` dumps and revalidates through that
    model, and this field is dropped before C1 ever sees it. Verified against
    C1's source. C1 needs no change and cannot break on this.

    HOW IT REACHES C3. Because C1 drops it, C2 re-attaches it to the
    AnomalyReport after C1 returns and before calling C3 (see
    `orchestration/pipeline.py`). C3's own AnomalyReport model sets
    `extra="allow"`, so it survives that crossing.

    ⚠️ THIS FIELD DOES NOTHING ON ITS OWN — C3 MUST STILL ACT.
    `c3_engine/narrative.py` builds a single prompt and has no persona
    concept, so today the value arrives and is ignored: narrative prose is
    IDENTICAL for both personas. C3 must read `anomaly_report.persona` and
    vary the prompt before the requirement is actually met. Until then, do
    not claim persona-tailored narratives in the deck or the demo. C2's own
    persona work is a rendering/entitlement distinction — a different, and
    separately defensible, claim.

    SEMANTIC CAVEAT. This describes the reader, not the company, so it sits
    oddly on CompanyInput. It is here because it is the only
    boundary-respecting route, not because it is the tidiest home.
    """

    EXECUTIVE = "executive"
    ANALYST = "analyst"


# ---------------------------------------------------------------------------
# Contract 1 — CompanyInput (Contract §4)
# produced by C2, consumed by C1. Schema owned by C1.
# ---------------------------------------------------------------------------


class DataPoint(BaseModel):
    period: str  # "YYYY-MM" | "YYYY-QN" | "YYYY"
    value: float
    interpolated: bool = False  # True if C2 gap-filled this point


class MetricEntry(BaseModel):
    metric_id: str  # MUST be canonical — C1 rejects unknown IDs
    granularity: Granularity  # AUTHORITATIVE over reporting_period.type
    values: list[DataPoint] = Field(min_length=1)
    confidence: float = 1.0  # 0-1
    source_system: Optional[str] = None
    grain: Optional[str] = None
    data_as_of: Optional[str] = None


class ReportingPeriod(BaseModel):
    type: Granularity  # envelope metadata only
    start: date
    end: date


class CompanyMetadata(BaseModel):
    name: str
    founded_year: Optional[int] = None
    employee_count: int
    annual_revenue: Optional[float] = None
    revenue_band: RevenueBand  # DERIVED by C2 from annual_revenue when present
    region: str


class CompanyInput(BaseModel):
    company_id: str
    sector_id: SectorId
    company_metadata: CompanyMetadata
    reporting_period: ReportingPeriod
    metrics: list[MetricEntry]
    raw_text_context: Optional[str] = None
    # ⚠️ C2-PROPOSED, UNSIGNED — see the Persona docstring above for the full
    # rationale, the C1 safety argument, and what C3 must still implement.
    # Optional with a None default on purpose: absent means "not declared"
    # (e.g. a direct POST /analyze), which is different from asserting a
    # persona for every submission. C2's own default lives on FormMetadata.
    persona: Optional[Persona] = None


# ---------------------------------------------------------------------------
# Contract 2 — AnomalyReport (Contract §5)
# produced by C1, consumed by C2 + C3. Schema owned by C1.
# ---------------------------------------------------------------------------


class TrendPoint(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    period: str
    value: float
    z_score: Optional[float] = None
    interpolated: bool = False


class DeviationDetail(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    observed_current: float
    expected_value: float  # BAND-ADJUSTED — not a universal sector median
    expected_std: float  # BAND-ADJUSTED
    z_score: Optional[float] = None
    percentile: float
    direction: DeviationDirection


class TrendDetail(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    direction: TrendDirection
    slope: Optional[float] = None
    acceleration: Optional[float] = None
    periods_deviating: Optional[int] = None
    values_over_time: Optional[list[TrendPoint]] = None
    # All Optionals are null when the metric has fewer than the trend-analysis
    # floor for its granularity (Contract §4.3 / master plan §7.2).


class Anomaly(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    anomaly_id: str
    metric_id: str
    metric_display_name: str
    category: str  # e.g. "revenue", "retention"
    severity_score: float  # 0-100
    severity_label: SeverityLabel
    deviation: DeviationDetail
    trend: TrendDetail
    correlated_anomalies: list[str] = []  # anomaly_ids — cluster seed, not a full graph (§5.3)
    noise_confidence: Optional[float] = None  # 0-1; P(signal), not P(noise)
    context_tags: list[str] = []  # fixed vocabulary — master plan §8.7 / Contract §5.3
    natural_language_summary: str  # template-generated by C1, NOT an LLM
    driver_rank: Optional[int] = None
    candidate_explanations: list[str] = []
    contribution_pct: Optional[float] = None
    source_system: Optional[str] = None
    data_as_of: Optional[str] = None


class HealthyHighlight(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    metric_id: str  # may be a COMPUTED id absent from metric config (e.g. ltv_cac_ratio)
    metric_display_name: Optional[str] = None
    status: Optional[str] = "healthy"  # e.g. "healthy"
    percentile: Optional[float] = None
    note: Optional[str] = None
    observed_value: Optional[float] = None
    expected_value: Optional[float] = None
    context_tags: Optional[list[str]] = None
    natural_language_summary: Optional[str] = None


class RefusalDetail(BaseModel):
    """UNVERIFIED — confirm against C1 repo. Only `reason` is confirmed against
    C1's source; `message` and `suggested_resolution` are C2's provisional
    additions (Contract §5.1, O13). `extra="allow"` is mandatory per the
    contract so real fields we failed to predict aren't silently dropped.

    C2's rendering logic must not depend on `message` being present — it
    generates fallback text from `reason` plus the original CompanyInput.
    Both provisional fields are therefore Optional even though the contract's
    prose shows `message` as a bare `str`.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    reason: RefusalReason  # CONFIRMED
    message: Optional[str] = None  # PROVISIONAL — see O13
    suggested_resolution: Optional[str] = None  # PROVISIONAL — see O13
    diagnostic_suggestion: Optional[str] = None
    required_data: Optional[str] = None
    missing_metrics: Optional[list[str]] = None


class ReportMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    model_version: str = "0.1.0-mvp"
    synthetic_profile_version: Optional[str] = None
    metrics_analyzed: Union[int, list[str]] = 0
    metrics_with_anomalies: Union[int, list[str]] = 0
    metrics_with_missing_data: Union[int, list[str]] = 0
    skipped_metrics: list[str] = []  # unrecognised metric_ids only — NOT the same as
    # silently-excluded noise-filtered metrics (Contract O11, still open).
    processing_time_ms: Union[int, float] = 0


class CompanyProfileSummary(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    revenue_band: RevenueBand
    employee_count: int
    region: Optional[str] = "NA"


class AnomalyReport(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_version: str = Field(default="anomaly_report_v1", alias="$schema")
    company_id: str
    sector_id: SectorId
    analysis_timestamp: Union[datetime, str]
    reporting_period: ReportingPeriod
    company_profile_summary: CompanyProfileSummary
    overall_health_score: Optional[float] = None  # NULL ON REFUSAL — bug #1, do not regress
    anomalies: list[Anomaly] = []
    non_anomalous_highlights: list[HealthyHighlight] = []
    refusal: Optional[RefusalDetail] = None
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)


# ---------------------------------------------------------------------------
# Contract 3 — EnrichedReport (Contract §6)
# produced by C3, consumed by C2. PROPOSED, C3 has not signed off (§11).
#
# Governing rule: C3 returns the AnomalyReport it received VERBATIM as a
# nested field. Enrichment is additive, never replacement (Contract §6.1).
# ---------------------------------------------------------------------------


class Adjustment(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target_metric_id: str
    target_display_name: str
    action: Literal["INCREASE", "DECREASE"]
    direction_symbol: Literal["+", "-"]
    current_value: Optional[float] = None  # NULL if not submitted — never invented (§6.4)
    current_value_source: Literal["submitted", "not_available"]
    target_value: float
    target_basis: str  # "profile_baseline" | "top_quartile" | ...
    delta: Optional[float] = None  # NULL when current_value is null
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    rationale: str


class Prescription(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    anomaly_id: str  # FK into anomaly_report.anomalies
    prescribed_adjustments: list[Adjustment]
    prescription_summary: str  # NOT "natural_language_summary" — name collision (§6.6)


class MatchedCase(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    case_id: str
    cluster_index: int
    similarity_score: float
    problem_description: str
    root_causes: list[str]
    recommended_actions: list[str]


class ActionItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    description: str
    impact: Literal["HIGH", "MEDIUM", "LOW"]
    effort: Literal["HIGH", "MEDIUM", "LOW"]
    evidence_anomaly_ids: list[str] = []


class Narrative(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    situation_summary: str
    likely_root_causes: list[str]
    prioritized_actions: list[ActionItem]
    positives: list[str]
    evidence_citations: list[str] = []


class EnrichmentMetadata(BaseModel):
    """degraded_reason — C2-PROPOSED v1.2, additive and optional. Not in the
    signed contract shape (Contract §6.2); flagged for announcement to C3
    alongside O7 (EnrichedReport sign-off still pending).

    Deliberately Optional[str], not an enum: this field can be set by either
    side (C2 when it wraps a bare AnomalyReport after a C1/C3 failure; C3
    itself per Contract §6.7, e.g. an LLM failure it handles internally with
    no exception ever reaching C2). An enum would turn an unrecognised value
    from the other component into a ValidationError — a hard failure exactly
    where degradation was supposed to be graceful.

    Conventional vocabulary (not enforced):
        C2 sets: c3_timeout | c3_failed | c3_contract_violation
        C3 sets: llm_failed | llm_timeout | case_match_failed
    Unknown values are logged and rendered generically, never rejected.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    llm_model: Optional[str] = None
    llm_tokens_used: Optional[int] = None
    processing_time_ms: Union[int, float] = 0
    cases_searched: int = 0
    cases_matched: int = 0
    unmatched_anomaly_ids: list[str] = []
    degraded: bool = False
    degraded_reason: Optional[str] = None


class EnrichedReport(BaseModel):
    # UNVERIFIED — the entire block is PROPOSED; C3 has not signed off (Contract §11).
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_version: str = Field(default="enriched_report_v1", alias="$schema")
    anomaly_report: AnomalyReport  # VERBATIM, UNTOUCHED
    prescriptions: list[Prescription] = []
    anomaly_clusters: list[list[str]] = []
    matched_cases: list[MatchedCase] = []
    narrative: Optional[Narrative] = None
    metadata: EnrichmentMetadata
