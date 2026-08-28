"""Canonical Input Schemas for businessintelligence.ai ML Engine.

Shared with API Layer and Input Parser developers.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


def _derive_revenue_band(revenue: float) -> "RevenueBand":
    if revenue < 1_000_000:
        return RevenueBand.UNDER_1M
    elif revenue < 10_000_000:
        return RevenueBand.ONE_TO_10M
    elif revenue <= 100_000_000:
        return RevenueBand.TEN_TO_100M
    else:
        return RevenueBand.OVER_100M


class SectorId(str, Enum):
    TECH_SAAS = "TECH_SAAS"
    RETAIL = "RETAIL"


class RevenueBand(str, Enum):
    UNDER_1M = "<1M"
    ONE_TO_10M = "1M-10M"
    TEN_TO_100M = "10M-100M"
    OVER_100M = ">100M"


class PeriodType(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class TimeSeriesPoint(BaseModel):
    """A single time series observation."""
    period: str = Field(..., description="Reporting period label, e.g. '2026-01' or '2026-Q1'")
    value: float = Field(..., description="Reported numeric metric value")
    interpolated: bool = Field(
        default=False,
        description="Whether this value was interpolated/estimated rather than directly observed"
    )


class MetricInput(BaseModel):
    """A metric series provided for a company."""
    metric_id: str = Field(..., description="Canonical metric ID, e.g. 'monthly_recurring_revenue_growth'")
    granularity: PeriodType = Field(default=PeriodType.MONTHLY, description="Time granularity of data points")
    values: List[TimeSeriesPoint] = Field(..., description="Time series data points (minimum 6 for full trend analysis)")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Source confidence score (1.0 = direct user entry, 0.7-0.9 = clean CSV, 0.4-0.6 = OCR/fuzzy)"
    )

    @field_validator("values")
    @classmethod
    def validate_values(cls, v: List[TimeSeriesPoint]) -> List[TimeSeriesPoint]:
        if not v:
            raise ValueError("Metric must contain at least one time series point")
        periods = [p.period for p in v]
        if len(periods) != len(set(periods)):
            raise ValueError("Duplicate period labels found in metric values")
        # Ensure chronological ordering by period label
        return sorted(v, key=lambda p: p.period)


class ReportingPeriod(BaseModel):
    """Overall reporting window for the company analysis."""
    type: PeriodType = Field(default=PeriodType.MONTHLY, description="Overall reporting cadence")
    start: str = Field(..., description="Start period or date, e.g. '2026-01-01'")
    end: str = Field(..., description="End period or date, e.g. '2026-06-30'")


class CompanyMetadata(BaseModel):
    """Company profile and demographic information."""
    name: str = Field(..., description="Company name")
    founded_year: Optional[int] = Field(default=None, description="Year founded")
    employee_count: int = Field(..., ge=1, description="Total employee headcount")
    annual_revenue: Optional[float] = Field(default=None, ge=0, description="Annual revenue in USD")
    revenue_band: RevenueBand = Field(..., description="Revenue band cohort")
    region: Optional[str] = Field(default="NA", description="Geographic region, e.g. 'NA', 'EU', 'APAC'")

    @model_validator(mode="after")
    def validate_revenue_band_consistency(self) -> "CompanyMetadata":
        if self.annual_revenue is not None:
            expected_band = _derive_revenue_band(self.annual_revenue)
            if self.revenue_band != expected_band:
                self.revenue_band = expected_band
        return self


class CompanyInput(BaseModel):
    """Root input payload for ML Engine analysis."""
    company_id: str = Field(..., description="Unique identifier for the company")
    sector_id: SectorId = Field(..., description="Target industry sector")
    company_metadata: CompanyMetadata = Field(..., description="Company profile metadata")
    reporting_period: ReportingPeriod = Field(..., description="Analysis time window")
    metrics: List[MetricInput] = Field(..., description="List of submitted metric series")
    raw_text_context: Optional[str] = Field(
        default=None,
        description="Optional unstructured notes or context from the user"
    )

    @field_validator("metrics")
    @classmethod
    def validate_metrics_not_empty(cls, v: List[MetricInput]) -> List[MetricInput]:
        if not v:
            raise ValueError("CompanyInput must contain at least one metric")
        return v
