"""Canonical Output Schemas for businessintelligence.ai ML Engine.

Shared with API Layer, Case-Based Reasoning, and LLM developers.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from .input_schema import SectorId, RevenueBand, ReportingPeriod


class SeverityLabel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    SEVERE = "SEVERE"


class DeviationDirection(str, Enum):
    ABOVE_EXPECTED = "above_expected"
    BELOW_EXPECTED = "below_expected"
    AS_EXPECTED = "as_expected"


class TrendDirection(str, Enum):
    DETERIORATING = "deteriorating"
    STABLE = "stable"
    IMPROVING = "improving"


class UrgencyLabel(str, Enum):
    ESCALATING = "escalating"
    STABLE_BAD = "stable_bad"
    IMPROVING = "improving"


class RefusalReason(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    LOW_CONFIDENCE = "low_confidence"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"


class TrendPoint(BaseModel):
    """A point in the trend timeline with its corresponding z-score."""
    period: str
    value: float
    z_score: float


class DeviationDetails(BaseModel):
    """Detailed statistical comparison against synthetic ideal baseline."""
    observed_current: float = Field(..., description="Latest observed value")
    expected_value: float = Field(..., description="Synthetic ideal expected mean")
    expected_std: float = Field(..., description="Synthetic standard deviation")
    z_score: float = Field(..., description="Number of standard deviations from expected mean")
    percentile: float = Field(..., description="CDF percentile in synthetic distribution (0-100)")
    direction: DeviationDirection = Field(..., description="Direction of deviation relative to expectation")


class TrendDetails(BaseModel):
    """Temporal dynamics and trajectory of the metric."""
    direction: TrendDirection = Field(..., description="Trajectory health impact")
    slope: Optional[float] = Field(
        default=None,
        description="Linear trend rate of change (null if <6 data points)"
    )
    acceleration: Optional[float] = Field(
        default=None,
        description="Second derivative / curvature of change (null if <6 data points)"
    )
    periods_deviating: Optional[int] = Field(
        default=None,
        description="Count of consecutive periods deviating beyond threshold (null if <6 data points)"
    )
    values_over_time: Optional[List[TrendPoint]] = Field(
        default=None,
        description="Historical trend evaluation points (null if <6 data points)"
    )


class AnomalyItem(BaseModel):
    """A detected and confirmed structural anomaly."""
    anomaly_id: str = Field(..., description="Unique identifier for the anomaly, e.g. 'anom_001'")
    metric_id: str = Field(..., description="Canonical metric ID")
    metric_display_name: str = Field(..., description="Human-readable metric name")
    category: str = Field(..., description="Metric category (e.g. revenue, unit_economics, efficiency)")
    severity_score: float = Field(..., ge=0.0, le=100.0, description="Composite severity score (0-100)")
    severity_label: SeverityLabel = Field(..., description="Exclusive severity band label")
    deviation: DeviationDetails = Field(..., description="Statistical deviation metrics")
    trend: TrendDetails = Field(..., description="Trend and trajectory analysis")
    correlated_anomalies: List[str] = Field(
        default_factory=list,
        description="IDs of related anomalies that co-deviated"
    )
    driver_rank: int = Field(
        default=0,
        description=(
            "Relative causal ranking among correlated anomalies. "
            "1 = most likely primary driver; 0 = likely symptom or uncorrelated."
        )
    )
    granger_tested: bool = Field(
        default=False,
        description="True if Granger causality test was applied for driver ranking. False = magnitude heuristic was used."
    )
    baseline_source: Literal["ets_personalised", "sector_parametric"] = Field(
        default="sector_parametric",
        description="Method used to produce the expected baseline for this anomaly"
    )
    candidate_explanations: List[str] = Field(
        default_factory=list,
        description=(
            "Competing deterministic explanations when noise_confidence < 0.5. "
            "Each string names a plausible hypothesis. Empty when confidence is high."
        )
    )
    decision_urgency: UrgencyLabel = Field(
        default=UrgencyLabel.STABLE_BAD,
        description=(
            "Time-urgency signal independent of severity magnitude. "
            "'escalating' = fast-worsening trajectory; 'stable_bad' = below baseline but not accelerating; 'improving' = recovering."
        )
    )
    noise_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence that this is a true structural anomaly rather than noise"
    )
    context_tags: List[str] = Field(
        default_factory=list,
        description="Semantic tags for vector and keyword case matching"
    )
    natural_language_summary: str = Field(
        ...,
        description="Deterministic executive summary of the anomaly for LLM prompts and reports"
    )
    contribution_pct: Optional[float] = Field(
        default=None,
        description=(
            "Percentage of the overall health score deterioration attributable to this anomaly. "
            "Computed as: (this_metric_weighted_severity / total_weighted_severity) * 100. "
            "Null when health score has not deteriorated (overall_health_score >= 50 or total == 0)."
        )
    )
    source_system: Optional[str] = Field(default=None, description="Originating source system, e.g. CRM, ERP")
    data_as_of: Optional[str] = Field(default=None, description="ISO date string of source data freshness")


class HighlightItem(BaseModel):
    """A healthy / non-anomalous metric highlight."""
    metric_id: str = Field(..., description="Canonical metric ID")
    status: str = Field(default="healthy", description="Status label")
    percentile: float = Field(..., description="Percentile ranking in synthetic distribution")
    note: str = Field(..., description="Brief explanatory note")


class RefusalDetails(BaseModel):
    """Structured refusal metadata when analysis cannot be performed."""
    reason: RefusalReason = Field(..., description="Category of refusal")
    message: str = Field(..., description="User-facing explanation of why analysis was refused")
    diagnostic_suggestion: str = Field(..., description="Actionable step to fix the input")
    missing_metrics: List[str] = Field(
        default_factory=list,
        description="List of required or missing metric IDs"
    )


class CompanyProfileSummary(BaseModel):
    """Summary of company profile used for synthetic baseline calibration."""
    revenue_band: RevenueBand
    employee_count: int
    region: Optional[str] = "NA"


class ReportMetadata(BaseModel):
    """Diagnostic and runtime metadata for the analysis."""
    model_version: str = "0.1.0-mvp"
    synthetic_profile_version: str = "2026-07-01"
    noise_filter_config: Dict[str, Any] = Field(default_factory=dict)
    metrics_analyzed: int = 0
    metrics_with_anomalies: int = 0
    metrics_with_missing_data: int = 0
    skipped_metrics: List[str] = Field(default_factory=list, description="Metric IDs provided in input that are not recognized for this sector")
    filtered_metrics: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Metrics that were submitted, recognized, but filtered out by the noise filter "
            "before becoming anomalies. Each entry: {'metric_id': str, 'reason': str, 'layer': 'L1'|'L2'|'L3'|'L4'}."
        )
    )
    processing_time_ms: int = 0


class AnomalyReport(BaseModel):
    """Root response object returned by ML Engine analyze_company()."""
    schema_version: str = Field(default="anomaly_report_v1", alias="$schema")
    company_id: str = Field(..., description="Company identifier")
    sector_id: SectorId = Field(..., description="Sector evaluated")
    analysis_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of analysis")
    reporting_period: ReportingPeriod = Field(..., description="Reporting time window analyzed")
    company_profile_summary: CompanyProfileSummary = Field(..., description="Calibrated company profile")
    overall_health_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Composite overall health score of the company (0-100), null if refusal"
    )
    anomalies: List[AnomalyItem] = Field(
        default_factory=list,
        description="List of confirmed structural anomalies, sorted by severity descending"
    )
    non_anomalous_highlights: List[HighlightItem] = Field(
        default_factory=list,
        description="Highlights of well-performing / healthy metrics"
    )
    refusal: Optional[RefusalDetails] = Field(
        default=None,
        description="Refusal payload if analysis was rejected"
    )
    metadata: ReportMetadata = Field(
        default_factory=ReportMetadata,
        description="Pipeline execution metadata"
    )

    model_config = ConfigDict(populate_by_name=True)
