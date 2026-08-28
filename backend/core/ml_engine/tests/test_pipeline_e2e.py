"""End-to-end integration tests for ml_engine pipeline."""

from ml_engine.models.input_schema import CompanyInput, SectorId
from ml_engine.models.output_schema import SeverityLabel
from ml_engine.pipeline import analyze_company


def test_e2e_saas_failing_company(sample_saas_failing_input: CompanyInput):
    """End-to-end test on SaaS company with declining MRR growth and spiking churn."""
    report = analyze_company(sample_saas_failing_input)

    assert report.company_id == "comp_saas_failing_01"
    assert report.sector_id == SectorId.TECH_SAAS
    assert report.refusal is None
    assert len(report.anomalies) >= 2

    # Check MRR growth anomaly
    mrr_anom = next((a for a in report.anomalies if a.metric_id == "monthly_recurring_revenue_growth"), None)
    assert mrr_anom is not None
    assert mrr_anom.severity_score >= 50.0
    assert mrr_anom.severity_label in [SeverityLabel.CRITICAL, SeverityLabel.SEVERE]
    assert mrr_anom.deviation.z_score < -2.5
    assert mrr_anom.trend.slope is not None
    assert mrr_anom.trend.slope < 0
    assert "declined" in mrr_anom.natural_language_summary

    # Check Churn anomaly
    churn_anom = next((a for a in report.anomalies if a.metric_id == "churn_rate"), None)
    assert churn_anom is not None
    assert churn_anom.severity_score >= 50.0

    # Check correlation linkage
    assert churn_anom.anomaly_id in mrr_anom.correlated_anomalies or mrr_anom.anomaly_id in churn_anom.correlated_anomalies

    # Check non-anomalous highlight for gross margin
    margin_highlight = next((h for h in report.non_anomalous_highlights if h.metric_id == "gross_margin"), None)
    assert margin_highlight is not None

    # Check latency
    assert report.metadata.processing_time_ms < 2000  # Strict budget is < 3000ms, typical is < 50ms


def test_e2e_retail_healthy_company(sample_retail_healthy_input: CompanyInput):
    """End-to-end test on healthy retail company."""
    report = analyze_company(sample_retail_healthy_input)

    assert report.company_id == "comp_retail_healthy_01"
    assert report.sector_id == SectorId.RETAIL
    assert report.refusal is None
    assert len(report.anomalies) == 0  # No severe anomalies
    assert len(report.non_anomalous_highlights) >= 1
    assert report.overall_health_score >= 60.0


def test_e2e_json_schema_export(sample_saas_failing_input: CompanyInput):
    """Ensure report can be cleanly converted to dictionary / JSON with $schema intact."""
    report = analyze_company(sample_saas_failing_input)
    dumped = report.model_dump(by_alias=True)
    assert "$schema" in dumped
    assert dumped["$schema"] == "anomaly_report_v1"


def test_e2e_ratio_highlights():
    """Verify LTV/CAC and revenue_per_employee highlights are generated when available."""
    from ml_engine.models.input_schema import CompanyMetadata, MetricInput, PeriodType, ReportingPeriod, RevenueBand, TimeSeriesPoint
    
    input_with_ltv_cac = CompanyInput(
        company_id="comp_saas_ratios",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="SaaS Metrics Corp",
            employee_count=50,
            annual_revenue=5_000_000.0,
            revenue_band=RevenueBand.ONE_TO_10M,
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01-01", end="2026-06-30"
        ),
        metrics=[
            MetricInput(
                metric_id="customer_acquisition_cost",
                values=[TimeSeriesPoint(period=f"2026-0{i}", value=4500.0) for i in range(1, 7)],
            ),
            MetricInput(
                metric_id="lifetime_value",
                values=[TimeSeriesPoint(period=f"2026-0{i}", value=22000.0) for i in range(1, 7)],
            ),
        ],
    )
    report = analyze_company(input_with_ltv_cac)
    assert report.refusal is None
    
    # Check LTV/CAC highlight (22000 / 4500 = 4.89x)
    ltv_cac_hl = next((h for h in report.non_anomalous_highlights if h.metric_id == "ltv_cac_ratio"), None)
    assert ltv_cac_hl is not None
    assert "4.89x" in ltv_cac_hl.note
    assert ltv_cac_hl.status == "healthy"

    # Check revenue per employee highlight (5,000,000 / 50 = $100,000)
    rev_emp_hl = next((h for h in report.non_anomalous_highlights if h.metric_id == "revenue_per_employee"), None)
    assert rev_emp_hl is not None
    assert "$100,000" in rev_emp_hl.note


def test_e2e_skipped_metrics_tracking():
    """Verify unknown metrics for a sector are tracked in metadata.skipped_metrics."""
    from ml_engine.models.input_schema import CompanyMetadata, MetricInput, PeriodType, ReportingPeriod, RevenueBand, TimeSeriesPoint

    input_with_foreign_metric = CompanyInput(
        company_id="comp_retail_foreign",
        sector_id=SectorId.RETAIL,
        company_metadata=CompanyMetadata(
            name="Retail Corp",
            employee_count=20,
            revenue_band=RevenueBand.ONE_TO_10M,
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01-01", end="2026-06-30"
        ),
        metrics=[
            MetricInput(
                metric_id="gross_margin",
                values=[TimeSeriesPoint(period=f"2026-0{i}", value=45.0) for i in range(1, 7)],
            ),
            MetricInput(
                metric_id="churn_rate",  # SaaS metric submitted to RETAIL
                values=[TimeSeriesPoint(period=f"2026-0{i}", value=2.0) for i in range(1, 7)],
            ),
        ],
    )
    report = analyze_company(input_with_foreign_metric)
    assert "churn_rate" in report.metadata.skipped_metrics
    assert report.metadata.metrics_with_missing_data >= 1


def test_e2e_summary_wording(sample_saas_failing_input: CompanyInput):
    """Verify natural language summary uses 'expected baseline' instead of 'sector median'."""
    report = analyze_company(sample_saas_failing_input)
    for anom in report.anomalies:
        assert "sector median" not in anom.natural_language_summary
        assert "expected baseline" in anom.natural_language_summary

