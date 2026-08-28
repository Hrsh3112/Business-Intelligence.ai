"""Synthetic anomaly injection test harness for validation."""

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
from ml_engine.models.output_schema import SeverityLabel
from ml_engine.pipeline import analyze_company


def test_injected_sudden_churn_spike():
    """Verify that a sudden sharp churn spike is detected as SEVERE/CRITICAL anomaly."""
    company_input = CompanyInput(
        company_id="comp_injected_churn",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="SaaS Flare",
            employee_count=50,
            revenue_band=RevenueBand.ONE_TO_10M,
        ),
        reporting_period=ReportingPeriod(
            start="2026-01-01",
            end="2026-06-30",
        ),
        metrics=[
            MetricInput(
                metric_id="churn_rate",
                values=[
                    TimeSeriesPoint(period="2026-01", value=2.0),
                    TimeSeriesPoint(period="2026-02", value=2.1),
                    TimeSeriesPoint(period="2026-03", value=2.2),
                    TimeSeriesPoint(period="2026-04", value=3.5),
                    TimeSeriesPoint(period="2026-05", value=6.0),
                    TimeSeriesPoint(period="2026-06", value=8.5),
                ],
                confidence=1.0,
            )
        ],
    )

    report = analyze_company(company_input)
    assert len(report.anomalies) == 1
    anom = report.anomalies[0]
    assert anom.metric_id == "churn_rate"
    assert anom.severity_score >= 60.0
    assert anom.deviation.z_score >= 4.0
    assert anom.trend.slope > 0  # Increasing churn is worse
    assert "risen from 2.0" in anom.natural_language_summary


def test_interpolated_points_downweighting():
    """Verify that interpolated data points reduce noise confidence and affect trajectory properly."""
    # Input with 50% interpolated points
    company_input = CompanyInput(
        company_id="comp_interpolated",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Interp SaaS",
            employee_count=40,
            revenue_band=RevenueBand.ONE_TO_10M,
        ),
        reporting_period=ReportingPeriod(
            start="2026-01-01",
            end="2026-06-30",
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                values=[
                    TimeSeriesPoint(period="2026-01", value=8.0, interpolated=False),
                    TimeSeriesPoint(period="2026-02", value=5.0, interpolated=True),
                    TimeSeriesPoint(period="2026-03", value=3.0, interpolated=True),
                    TimeSeriesPoint(period="2026-04", value=0.0, interpolated=False),
                    TimeSeriesPoint(period="2026-05", value=-2.0, interpolated=True),
                    TimeSeriesPoint(period="2026-06", value=-4.0, interpolated=False),
                ],
                confidence=0.8,
            )
        ],
    )

    report = analyze_company(company_input)
    assert len(report.anomalies) == 1
    assert report.metadata.metrics_with_missing_data == 1
    assert report.anomalies[0].noise_confidence < 0.95  # Penalized for interpolation


def test_low_data_confidence_score_moderation():
    """Verify that lower data source confidence moderates severity score appropriately."""
    base_points = [
        TimeSeriesPoint(period=f"2026-0{i+1}", value=float(10 - i * 3))
        for i in range(6)
    ]

    inp_high_conf = CompanyInput(
        company_id="comp_high_conf",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(name="Conf A", employee_count=50, revenue_band=RevenueBand.ONE_TO_10M),
        reporting_period=ReportingPeriod(start="2026-01-01", end="2026-06-30"),
        metrics=[MetricInput(metric_id="monthly_recurring_revenue_growth", values=base_points, confidence=1.0)],
    )

    inp_low_conf = CompanyInput(
        company_id="comp_low_conf",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(name="Conf B", employee_count=50, revenue_band=RevenueBand.ONE_TO_10M),
        reporting_period=ReportingPeriod(start="2026-01-01", end="2026-06-30"),
        metrics=[MetricInput(metric_id="monthly_recurring_revenue_growth", values=base_points, confidence=0.4)],
    )

    rep_high = analyze_company(inp_high_conf)
    rep_low = analyze_company(inp_low_conf)

    assert rep_high.anomalies[0].severity_score > rep_low.anomalies[0].severity_score
