from datetime import datetime, date
from typing import Literal, Optional, Any, Union
from pydantic import BaseModel, ConfigDict, Field

class ReportingPeriod(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    type: Literal["monthly", "quarterly", "annual"]
    start: Union[date, str]
    end: Union[date, str]

class CompanyProfileSummary(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    revenue_band: str
    employee_count: int
    region: Optional[str] = "NA"

class DeviationDetail(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    observed_current: float
    expected_value: float
    expected_std: float
    z_score: float
    percentile: float
    direction: Literal["above_expected", "below_expected", "as_expected"]

class TrendPoint(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    period: str
    value: float
    z_score: Optional[float] = None
    interpolated: bool = False

class TrendDetail(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    direction: Literal["improving", "stable", "deteriorating"]
    slope: Optional[float] = None
    acceleration: Optional[float] = None
    periods_deviating: Optional[int] = None
    values_over_time: Optional[list[TrendPoint]] = None

class Anomaly(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    anomaly_id: str
    metric_id: str
    metric_display_name: str
    category: str
    severity_score: float
    severity_label: Literal["INFO", "WARNING", "CRITICAL", "SEVERE"]
    deviation: DeviationDetail
    trend: TrendDetail
    correlated_anomalies: list[str] = []
    noise_confidence: float
    context_tags: list[str] = []
    natural_language_summary: str

class HealthyHighlight(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    metric_id: str
    metric_display_name: Optional[str] = None
    status: Optional[str] = "healthy"
    percentile: Optional[float] = None
    note: Optional[str] = None
    observed_value: Optional[float] = None
    expected_value: Optional[float] = None
    context_tags: Optional[list[str]] = None
    natural_language_summary: Optional[str] = None

class RefusalDetail(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    reason: str
    message: Optional[str] = None
    required_data: Optional[str] = None
    suggested_resolution: Optional[str] = None
    diagnostic_suggestion: Optional[str] = None
    missing_metrics: Optional[list[str]] = None

class ReportMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    model_version: str = "0.1.0-mvp"
    synthetic_profile_version: Optional[str] = None
    metrics_analyzed: Union[int, list[str]] = 0
    metrics_with_anomalies: Union[int, list[str]] = 0
    metrics_with_missing_data: Union[int, list[str]] = 0
    skipped_metrics: list[str] = []
    processing_time_ms: Union[int, float] = 0

class AnomalyReport(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    schema_version: str = Field(default="anomaly_report_v1", alias="$schema")
    company_id: str
    sector_id: str
    analysis_timestamp: Union[datetime, str]
    reporting_period: ReportingPeriod
    company_profile_summary: CompanyProfileSummary
    overall_health_score: Optional[float] = None
    anomalies: list[Anomaly] = []
    non_anomalous_highlights: list[HealthyHighlight] = []
    refusal: Optional[RefusalDetail] = None
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)


class Adjustment(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    target_metric_id: str
    target_display_name: str
    action: Literal["INCREASE", "DECREASE"]
    direction_symbol: Literal["+", "-"]
    current_value: Optional[float] = None
    current_value_source: Literal["submitted", "not_available"]
    target_value: float
    target_basis: str
    delta: Optional[float] = None
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    rationale: str

class Prescription(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    anomaly_id: str
    prescribed_adjustments: list[Adjustment]
    prescription_summary: str

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

class Narrative(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    situation_summary: str
    likely_root_causes: list[str]
    prioritized_actions: list[ActionItem]
    positives: list[str]

class EnrichmentMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    llm_model: Optional[str] = None
    llm_tokens_used: Optional[int] = None
    processing_time_ms: float = 0.0
    cases_searched: int = 0
    cases_matched: int = 0
    unmatched_anomaly_ids: list[str] = []
    degraded: bool = False
    degraded_reason: Optional[str] = None

class EnrichedReport(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    schema_version: str = Field(default="enriched_report_v1", alias="$schema")
    anomaly_report: AnomalyReport
    prescriptions: list[Prescription] = []
    anomaly_clusters: list[list[str]] = []
    matched_cases: list[MatchedCase] = []
    narrative: Optional[Narrative] = None
    metadata: EnrichmentMetadata
