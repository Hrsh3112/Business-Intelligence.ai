"""Pytest fixtures and sample inputs for ml_engine testing."""

import pytest
from ml_engine.models.input_schema import (
    CompanyInput,
    CompanyMetadata,
    MetricInput,
    PeriodType,
    ReportingPeriod,
    RevenueBand,
    SectorId,
    TimeSeriesPoint,
)


@pytest.fixture
def sample_saas_failing_input() -> CompanyInput:
    """A SaaS company experiencing sharp MRR growth decline and churn rate spike."""
    return CompanyInput(
        company_id="comp_saas_failing_01",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="CloudScale Analytics",
            founded_year=2020,
            employee_count=120,
            annual_revenue=6500000.0,
            revenue_band=RevenueBand.ONE_TO_10M,
            region="NA",
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY,
            start="2026-01-01",
            end="2026-06-30",
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                granularity=PeriodType.MONTHLY,
                values=[
                    TimeSeriesPoint(period="2026-01", value=7.2, interpolated=False),
                    TimeSeriesPoint(period="2026-02", value=6.5, interpolated=False),
                    TimeSeriesPoint(period="2026-03", value=4.1, interpolated=False),
                    TimeSeriesPoint(period="2026-04", value=2.3, interpolated=False),
                    TimeSeriesPoint(period="2026-05", value=-1.2, interpolated=False),
                    TimeSeriesPoint(period="2026-06", value=-3.5, interpolated=False),
                ],
                confidence=0.95,
            ),
            MetricInput(
                metric_id="churn_rate",
                granularity=PeriodType.MONTHLY,
                values=[
                    TimeSeriesPoint(period="2026-01", value=1.8, interpolated=False),
                    TimeSeriesPoint(period="2026-02", value=2.1, interpolated=False),
                    TimeSeriesPoint(period="2026-03", value=2.9, interpolated=False),
                    TimeSeriesPoint(period="2026-04", value=3.8, interpolated=False),
                    TimeSeriesPoint(period="2026-05", value=4.5, interpolated=False),
                    TimeSeriesPoint(period="2026-06", value=5.2, interpolated=False),
                ],
                confidence=0.90,
            ),
            MetricInput(
                metric_id="gross_margin",
                granularity=PeriodType.MONTHLY,
                values=[
                    TimeSeriesPoint(period="2026-01", value=76.0, interpolated=False),
                    TimeSeriesPoint(period="2026-02", value=75.5, interpolated=False),
                    TimeSeriesPoint(period="2026-03", value=75.0, interpolated=False),
                    TimeSeriesPoint(period="2026-04", value=75.8, interpolated=False),
                    TimeSeriesPoint(period="2026-05", value=74.9, interpolated=False),
                    TimeSeriesPoint(period="2026-06", value=75.2, interpolated=False),
                ],
                confidence=1.0,
            ),
        ],
        raw_text_context="Customer feedback indicates product stability issues in Q2 resulting in cancellations.",
    )


@pytest.fixture
def sample_retail_healthy_input() -> CompanyInput:
    """A healthy retail company with strong gross margins and steady inventory turns."""
    return CompanyInput(
        company_id="comp_retail_healthy_01",
        sector_id=SectorId.RETAIL,
        company_metadata=CompanyMetadata(
            name="Urban Trends Apparel",
            founded_year=2015,
            employee_count=85,
            annual_revenue=12000000.0,
            revenue_band=RevenueBand.TEN_TO_100M,
            region="NA",
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY,
            start="2026-01-01",
            end="2026-06-30",
        ),
        metrics=[
            MetricInput(
                metric_id="gross_margin",
                granularity=PeriodType.MONTHLY,
                values=[
                    TimeSeriesPoint(period="2026-01", value=46.0, interpolated=False),
                    TimeSeriesPoint(period="2026-02", value=45.5, interpolated=False),
                    TimeSeriesPoint(period="2026-03", value=47.0, interpolated=False),
                    TimeSeriesPoint(period="2026-04", value=46.8, interpolated=False),
                    TimeSeriesPoint(period="2026-05", value=48.2, interpolated=False),
                    TimeSeriesPoint(period="2026-06", value=47.5, interpolated=False),
                ],
                confidence=1.0,
            ),
            MetricInput(
                metric_id="inventory_turnover",
                granularity=PeriodType.MONTHLY,
                values=[
                    TimeSeriesPoint(period="2026-01", value=7.0, interpolated=False),
                    TimeSeriesPoint(period="2026-02", value=7.2, interpolated=False),
                    TimeSeriesPoint(period="2026-03", value=7.1, interpolated=False),
                    TimeSeriesPoint(period="2026-04", value=7.5, interpolated=False),
                    TimeSeriesPoint(period="2026-05", value=7.4, interpolated=False),
                    TimeSeriesPoint(period="2026-06", value=7.6, interpolated=False),
                ],
                confidence=0.95,
            ),
        ],
    )


@pytest.fixture
def sample_short_series_input() -> CompanyInput:
    """A company submission with fewer than 6 periods (refusal scenario)."""
    return CompanyInput(
        company_id="comp_short_01",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Early Startup Inc",
            employee_count=10,
            revenue_band=RevenueBand.UNDER_1M,
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY,
            start="2026-04-01",
            end="2026-06-30",
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                values=[
                    TimeSeriesPoint(period="2026-04", value=12.0),
                    TimeSeriesPoint(period="2026-05", value=10.5),
                    TimeSeriesPoint(period="2026-06", value=9.0),
                ],
            )
        ],
    )
