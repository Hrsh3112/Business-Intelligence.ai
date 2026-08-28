"""Tests for Pydantic input and output models."""

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
from ml_engine.models.output_schema import (
    AnomalyItem,
    AnomalyReport,
    CompanyProfileSummary,
    DeviationDetails,
    DeviationDirection,
    SeverityLabel,
    TrendDetails,
    TrendDirection,
)


def test_company_input_serialization(sample_saas_failing_input: CompanyInput):
    """Ensure CompanyInput serializes and deserializes cleanly."""
    json_data = sample_saas_failing_input.model_dump_json()
    reconstructed = CompanyInput.model_validate_json(json_data)
    assert reconstructed.company_id == "comp_saas_failing_01"
    assert reconstructed.sector_id == SectorId.TECH_SAAS
    assert len(reconstructed.metrics) == 3


def test_empty_metrics_validation():
    """Ensure validation fails if metrics list is empty."""
    with pytest.raises(ValueError):
        CompanyInput(
            company_id="comp_empty",
            sector_id=SectorId.TECH_SAAS,
            company_metadata=CompanyMetadata(
                name="Empty Corp",
                employee_count=10,
                revenue_band=RevenueBand.UNDER_1M,
            ),
            reporting_period=ReportingPeriod(
                type=PeriodType.MONTHLY,
                start="2026-01-01",
                end="2026-06-30",
            ),
            metrics=[],
        )


def test_anomaly_report_serialization():
    """Ensure AnomalyReport serializes with proper schema version alias."""
    report = AnomalyReport(
        company_id="comp_test",
        sector_id=SectorId.TECH_SAAS,
        analysis_timestamp="2026-07-15T14:30:00Z",
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY,
            start="2026-01-01",
            end="2026-06-30",
        ),
        company_profile_summary=CompanyProfileSummary(
            revenue_band=RevenueBand.ONE_TO_10M,
            employee_count=100,
        ),
        overall_health_score=68.5,
        anomalies=[
            AnomalyItem(
                anomaly_id="anom_001",
                metric_id="monthly_recurring_revenue_growth",
                metric_display_name="MRR Growth Rate (%)",
                category="revenue",
                severity_score=72.0,
                severity_label=SeverityLabel.CRITICAL,
                deviation=DeviationDetails(
                    observed_current=-3.5,
                    expected_value=8.5,
                    expected_std=3.2,
                    z_score=-3.75,
                    percentile=2.1,
                    direction=DeviationDirection.BELOW_EXPECTED,
                ),
                trend=TrendDetails(
                    direction=TrendDirection.DETERIORATING,
                    slope=-2.1,
                    acceleration=-0.3,
                    periods_deviating=4,
                ),
                noise_confidence=0.92,
                natural_language_summary="MRR growth declined sharply.",
            )
        ],
    )

    dumped = report.model_dump(by_alias=True)
    assert dumped["$schema"] == "anomaly_report_v1"
    assert len(dumped["anomalies"]) == 1
    assert dumped["anomalies"][0]["severity_label"] == "CRITICAL"


def test_duplicate_periods_rejection():
    """Ensure duplicate period labels within a metric raise ValueError."""
    with pytest.raises(ValueError, match="Duplicate period labels"):
        MetricInput(
            metric_id="churn_rate",
            values=[
                TimeSeriesPoint(period="2026-01", value=2.0),
                TimeSeriesPoint(period="2026-01", value=2.5),  # duplicate
            ],
        )


def test_period_auto_sorting():
    """Ensure submitted time series points are automatically sorted chronologically."""
    metric = MetricInput(
        metric_id="churn_rate",
        values=[
            TimeSeriesPoint(period="2026-03", value=3.0),
            TimeSeriesPoint(period="2026-01", value=1.0),
            TimeSeriesPoint(period="2026-02", value=2.0),
        ],
    )
    periods = [p.period for p in metric.values]
    assert periods == ["2026-01", "2026-02", "2026-03"]
    values = [p.value for p in metric.values]
    assert values == [1.0, 2.0, 3.0]


def test_revenue_band_auto_derivation():
    """Ensure revenue_band is calibrated consistently if annual_revenue is provided."""
    # User provides $500K but mistakenly specifies >100M -> should calibrate to <1M
    meta = CompanyMetadata(
        name="Small SaaS",
        employee_count=10,
        annual_revenue=500_000,
        revenue_band=RevenueBand.OVER_100M,
    )
    assert meta.revenue_band == RevenueBand.UNDER_1M

    # When annual_revenue is None, user-specified band is preserved
    meta_no_rev = CompanyMetadata(
        name="Mystery SaaS",
        employee_count=10,
        annual_revenue=None,
        revenue_band=RevenueBand.TEN_TO_100M,
    )
    assert meta_no_rev.revenue_band == RevenueBand.TEN_TO_100M

