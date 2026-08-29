"""Tests for refusal evaluation."""

from ml_engine.anomaly.refusal import RefusalEvaluator
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
from ml_engine.models.output_schema import RefusalReason
from ml_engine.pipeline import analyze_company


def test_refusal_on_short_series(sample_short_series_input: CompanyInput):
    """Verify refusal triggers when all submitted metrics have < 6 data points."""
    refusal = RefusalEvaluator.evaluate_refusal(sample_short_series_input, min_periods_required=6)
    assert refusal is not None
    assert refusal.reason == RefusalReason.INSUFFICIENT_DATA
    assert "required periods" in refusal.message

    # Test pipeline end-to-end with short series
    report = analyze_company(sample_short_series_input)
    assert report.refusal is not None
    assert report.refusal.reason == RefusalReason.INSUFFICIENT_DATA
    assert report.overall_health_score is None  # Bug fix verified: null on refusal
    assert len(report.anomalies) == 0


def test_no_refusal_when_at_least_one_metric_has_6_periods(sample_saas_failing_input: CompanyInput):
    """Verify refusal does NOT trigger when valid 6-period series exists."""
    refusal = RefusalEvaluator.evaluate_refusal(sample_saas_failing_input, min_periods_required=6)
    assert refusal is None


def test_granularity_aware_refusal():
    """Verify granularity-aware thresholds (6 monthly / 4 quarterly / 3 annual)."""
    min_periods_map = {"monthly": 6, "quarterly": 4, "annual": 3}

    # 3 quarterly points -> refusal (needs 4)
    q3_input = CompanyInput(
        company_id="comp_q3",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Q Corp", employee_count=50, revenue_band=RevenueBand.ONE_TO_10M
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.QUARTERLY, start="2025-Q1", end="2025-Q3"
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                granularity=PeriodType.QUARTERLY,
                values=[
                    TimeSeriesPoint(period="2025-Q1", value=5.0),
                    TimeSeriesPoint(period="2025-Q2", value=4.0),
                    TimeSeriesPoint(period="2025-Q3", value=3.0),
                ],
            )
        ],
    )
    refusal_q3 = RefusalEvaluator.evaluate_refusal(q3_input, min_periods_required=min_periods_map)
    assert refusal_q3 is not None
    assert refusal_q3.reason == RefusalReason.INSUFFICIENT_DATA

    # 4 quarterly points -> no refusal
    q4_input = CompanyInput(
        company_id="comp_q4",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Q Corp", employee_count=50, revenue_band=RevenueBand.ONE_TO_10M
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.QUARTERLY, start="2025-Q1", end="2025-Q4"
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                granularity=PeriodType.QUARTERLY,
                values=[
                    TimeSeriesPoint(period="2025-Q1", value=5.0),
                    TimeSeriesPoint(period="2025-Q2", value=4.0),
                    TimeSeriesPoint(period="2025-Q3", value=3.0),
                    TimeSeriesPoint(period="2025-Q4", value=2.0),
                ],
            )
        ],
    )
    refusal_q4 = RefusalEvaluator.evaluate_refusal(q4_input, min_periods_required=min_periods_map)
    assert refusal_q4 is None

    # 3 annual points -> no refusal
    a3_input = CompanyInput(
        company_id="comp_a3",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="A Corp", employee_count=50, revenue_band=RevenueBand.ONE_TO_10M
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.ANNUAL, start="2023", end="2025"
        ),
        metrics=[
            MetricInput(
                metric_id="gross_margin",
                granularity=PeriodType.ANNUAL,
                values=[
                    TimeSeriesPoint(period="2023", value=75.0),
                    TimeSeriesPoint(period="2024", value=76.0),
                    TimeSeriesPoint(period="2025", value=74.0),
                ],
            )
        ],
    )
    refusal_a3 = RefusalEvaluator.evaluate_refusal(a3_input, min_periods_required=min_periods_map)
    assert refusal_a3 is None


def test_low_confidence_refusal():
    """Verify refusal triggers when all metrics have confidence < 0.35."""
    low_conf_input = CompanyInput(
        company_id="comp_low_conf",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Low Conf Corp", employee_count=50, revenue_band=RevenueBand.ONE_TO_10M
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01", end="2026-06"
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                confidence=0.2,
                values=[
                    TimeSeriesPoint(period="2026-01", value=5.0),
                    TimeSeriesPoint(period="2026-02", value=4.0),
                    TimeSeriesPoint(period="2026-03", value=3.0),
                    TimeSeriesPoint(period="2026-04", value=2.0),
                    TimeSeriesPoint(period="2026-05", value=1.0),
                    TimeSeriesPoint(period="2026-06", value=0.0),
                ],
            )
        ],
    )
    refusal = RefusalEvaluator.evaluate_refusal(low_conf_input)
    assert refusal is not None
    assert refusal.reason == RefusalReason.LOW_CONFIDENCE


def test_sparse_history_newly_launched_kpi_message():
    """Verify refusal message specifically calls out newly launched or sparse-history KPI."""
    sparse_input = CompanyInput(
        company_id="comp_sparse_kpi",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Sparse Corp", employee_count=10, revenue_band=RevenueBand.UNDER_1M
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-04", end="2026-06"
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                values=[
                    TimeSeriesPoint(period="2026-04", value=5.0),
                    TimeSeriesPoint(period="2026-05", value=4.0),
                    TimeSeriesPoint(period="2026-06", value=3.0),
                ],
            )
        ],
    )
    report = analyze_company(sparse_input)
    assert report.refusal is not None
    assert report.refusal.reason == RefusalReason.INSUFFICIENT_DATA
    assert "sparse-history" in report.refusal.message or "newly launched" in report.refusal.message


def test_contradictory_evidence_refusal():
    """Verify contradictory evidence refusal fires when positively correlated metrics deviate in opposite directions."""
    from ml_engine.synthetic.correlations import CorrelationEngine
    from ml_engine.config.loader import load_sector_config
    from ml_engine.models.internal import MetricDeviation
    from ml_engine.models.output_schema import AnomalyItem, DeviationDetails, DeviationDirection, TrendDetails, TrendDirection

    saas_cfg = load_sector_config("TECH_SAAS")
    corr_engine = CorrelationEngine(saas_cfg)

    # monthly_recurring_revenue_growth and net_revenue_retention have positive correlation 0.78
    # If MRR growth is severely anomalous with z = -3.0 (crashing), but NRR is anomalous with z = +3.0 (surging)
    # co_dev_sign = -3.0 * 3.0 * 0.78 = -7.02 (strongly negative despite positive correlation)
    anom1 = AnomalyItem(
        anomaly_id="anom_001",
        metric_id="monthly_recurring_revenue_growth",
        metric_display_name="MRR Growth",
        category="revenue",
        severity_score=80.0,
        severity_label="SEVERE",
        deviation=DeviationDetails(
            observed_current=-5.0,
            expected_value=8.5,
            expected_std=3.2,
            z_score=-3.0,
            percentile=0.1,
            direction=DeviationDirection.BELOW_EXPECTED,
        ),
        trend=TrendDetails(direction=TrendDirection.DETERIORATING),
        noise_confidence=0.85,
        natural_language_summary="MRR growth declined sharply",
    )

    dev_map = {
        "monthly_recurring_revenue_growth": MetricDeviation(
            metric_id="monthly_recurring_revenue_growth",
            observed_value=-5.0,
            expected_mean=8.5,
            expected_std=3.2,
            z_score=-3.0,
            percentile=0.1,
            direction=DeviationDirection.BELOW_EXPECTED,
            severity_raw=80.0,
        ),
        "net_revenue_retention": MetricDeviation(
            metric_id="net_revenue_retention",
            observed_value=140.0,
            expected_mean=105.0,
            expected_std=10.0,
            z_score=3.5,
            percentile=99.9,
            direction=DeviationDirection.ABOVE_EXPECTED,
            severity_raw=80.0,
        ),
    }

    refusal = RefusalEvaluator.evaluate_contradictory_evidence(
        anomalies=[anom1],
        deviations_map=dev_map,
        correlation_engine=corr_engine,
        threshold=0.5,
    )
    assert refusal is not None
    assert refusal.reason == RefusalReason.CONTRADICTORY_EVIDENCE
    assert "contradictory" in refusal.message.lower()

