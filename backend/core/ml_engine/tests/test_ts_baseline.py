"""Tests for Holt-Winters ETS personalised time-series baseline."""

import pytest
from ml_engine.synthetic.ts_baseline import fit_ets_baseline
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
from ml_engine.pipeline import analyze_company


def test_ets_forecast_returns_floats():
    """Smoke test: 8 periods of historical data should return forecast mean and non-zero std."""
    values = [10.0, 11.2, 12.1, 13.0, 14.5, 15.1, 16.0, 17.2]
    mean, std = fit_ets_baseline(values)
    assert isinstance(mean, float)
    assert isinstance(std, float)
    assert std > 0.0
    # The next step forecast should continue the upward trend roughly
    assert mean > 15.0


def test_ets_raises_on_short_series():
    """Assert ValueError is raised when series length < 6."""
    short_values = [10.0, 11.0, 12.0, 13.0]
    with pytest.raises(ValueError, match="ETS baseline requires >= 6 periods"):
        fit_ets_baseline(short_values)


def test_ets_baseline_used_when_history_sufficient():
    """When a metric has >= 7 periods (>= 6 prior history periods), pipeline should use ets_personalised baseline."""
    periods = [f"2025-0{i}" for i in range(1, 9)]
    # 6 baseline periods of ~2.0% churn, then 2 periods of 8.0% spike (passes persistence filter)
    vals = [2.0, 2.1, 1.9, 2.0, 2.2, 2.0, 8.0, 8.5]
    data_points = [TimeSeriesPoint(period=p, value=v) for p, v in zip(periods, vals)]

    metric = MetricInput(
        metric_id="churn_rate",
        granularity=PeriodType.MONTHLY,
        confidence=1.0,
        source_system="CRM",
        values=data_points,
    )
    arr_points = [TimeSeriesPoint(period=p, value=100000.0) for p in periods]
    arr_metric = MetricInput(
        metric_id="annual_recurring_revenue",
        granularity=PeriodType.MONTHLY,
        confidence=1.0,
        source_system="ERP",
        values=arr_points,
    )

    company = CompanyInput(
        company_id="comp_ets_test",
        sector_id=SectorId.TECH_SAAS,
        reporting_period=ReportingPeriod(type=PeriodType.MONTHLY, start="2025-01-01", end="2025-08-31"),
        company_metadata=CompanyMetadata(
            name="ETS Test Co",
            revenue_band=RevenueBand.ONE_TO_10M,
            employee_count=50,
        ),
        metrics=[metric, arr_metric],
    )

    report = analyze_company(company)
    assert report.refusal is None
    anom = next((a for a in report.anomalies if a.metric_id == "churn_rate"), None)
    assert anom is not None
    assert anom.baseline_source == "ets_personalised"


def test_sector_parametric_used_as_fallback():
    """When a metric has < 7 periods (e.g. 4 quarterly periods), sector_parametric should be used."""
    periods = ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]
    # Spiking churn for last 2 quarters to pass persistence
    vals = [2.0, 2.0, 8.0, 8.5]
    data_points = [TimeSeriesPoint(period=p, value=v) for p, v in zip(periods, vals)]

    metric = MetricInput(
        metric_id="churn_rate",
        granularity=PeriodType.QUARTERLY,
        confidence=1.0,
        source_system="CRM",
        values=data_points,
    )
    arr_points = [TimeSeriesPoint(period=p, value=100000.0) for p in periods]
    arr_metric = MetricInput(
        metric_id="annual_recurring_revenue",
        granularity=PeriodType.QUARTERLY,
        confidence=1.0,
        source_system="ERP",
        values=arr_points,
    )

    company = CompanyInput(
        company_id="comp_fallback_test",
        sector_id=SectorId.TECH_SAAS,
        reporting_period=ReportingPeriod(type=PeriodType.QUARTERLY, start="2025-01-01", end="2025-12-31"),
        company_metadata=CompanyMetadata(
            name="Fallback Test Co",
            revenue_band=RevenueBand.ONE_TO_10M,
            employee_count=50,
        ),
        metrics=[metric, arr_metric],
    )

    report = analyze_company(company)
    assert report.refusal is None
    anom = next((a for a in report.anomalies if a.metric_id == "churn_rate"), None)
    assert anom is not None
    assert anom.baseline_source == "sector_parametric"
