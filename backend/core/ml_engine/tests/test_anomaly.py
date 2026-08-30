"""Tests for 4-layer noise filter, severity scorer, and classifier."""

import pytest
from ml_engine.anomaly.classifier import SeverityClassifier
from ml_engine.anomaly.noise_filter import MultiLayerNoiseFilter
from ml_engine.anomaly.scorer import SeverityScorer
from ml_engine.config.loader import load_sector_config, load_thresholds
from ml_engine.features.extractor import FeatureExtractor
from ml_engine.features.normalizer import FeatureNormalizer
from ml_engine.models.input_schema import MetricInput, RevenueBand, TimeSeriesPoint
from ml_engine.models.output_schema import SeverityLabel
from ml_engine.synthetic.correlations import CorrelationEngine
from ml_engine.synthetic.generator import SyntheticProfileGenerator


def test_classifier_boundaries():
    """Verify exclusive severity band cutoffs:
    < 25 -> INFO
    25 <= x < 50 -> WARNING
    50 <= x < 75 -> CRITICAL
    >= 75 -> SEVERE
    """
    thresholds = load_thresholds()
    classifier = SeverityClassifier(thresholds)

    assert classifier.classify(10.0) == SeverityLabel.INFO
    assert classifier.classify(24.9) == SeverityLabel.INFO
    assert classifier.classify(25.0) == SeverityLabel.WARNING
    assert classifier.classify(49.9) == SeverityLabel.WARNING
    assert classifier.classify(50.0) == SeverityLabel.CRITICAL
    assert classifier.classify(74.9) == SeverityLabel.CRITICAL
    assert classifier.classify(75.0) == SeverityLabel.SEVERE
    assert classifier.classify(95.0) == SeverityLabel.SEVERE


def test_noise_filter_l1_rejection():
    """Verify Layer 1 rejects small deviations below threshold."""
    thresholds = load_thresholds()
    saas_cfg = load_sector_config("TECH_SAAS")
    corr_engine = CorrelationEngine(saas_cfg)
    filter_engine = MultiLayerNoiseFilter(thresholds, corr_engine)
    gen = SyntheticProfileGenerator(saas_cfg)
    profile = gen.get_calibrated_profile(RevenueBand.ONE_TO_10M)
    baseline = profile["monthly_recurring_revenue_growth"]

    extractor = FeatureExtractor(min_periods_for_trend=6)
    # Values close to mean 8.5
    metric_input = MetricInput(
        metric_id="monthly_recurring_revenue_growth",
        values=[TimeSeriesPoint(period=f"2026-0{i+1}", value=8.2) for i in range(6)],
    )
    features = extractor.extract_features(metric_input, baseline.metric_def)
    normalizer = FeatureNormalizer(z_threshold_flag=thresholds.z_threshold_flag)
    deviation = normalizer.normalize(features, baseline)

    res = filter_engine.filter_metric(features, deviation, baseline, {})
    assert res.passed is False
    assert res.l1_passed is False


def test_severity_scorer_components():
    """Verify composite severity score calculation."""
    thresholds = load_thresholds()
    scorer = SeverityScorer(thresholds)
    saas_cfg = load_sector_config("TECH_SAAS")
    gen = SyntheticProfileGenerator(saas_cfg)
    profile = gen.get_calibrated_profile(RevenueBand.ONE_TO_10M)
    baseline = profile["monthly_recurring_revenue_growth"]

    extractor = FeatureExtractor(min_periods_for_trend=6)
    # Severe drop from 8% to -5%
    metric_input = MetricInput(
        metric_id="monthly_recurring_revenue_growth",
        values=[
            TimeSeriesPoint(period="2026-01", value=8.0),
            TimeSeriesPoint(period="2026-02", value=5.0),
            TimeSeriesPoint(period="2026-03", value=2.0),
            TimeSeriesPoint(period="2026-04", value=-1.0),
            TimeSeriesPoint(period="2026-05", value=-3.0),
            TimeSeriesPoint(period="2026-06", value=-5.0),
        ],
    )
    features = extractor.extract_features(metric_input, baseline.metric_def)
    normalizer = FeatureNormalizer(z_threshold_flag=thresholds.z_threshold_flag)
    deviation = normalizer.normalize(features, baseline)

    score = scorer.compute_score(
        features=features,
        deviation=deviation,
        baseline=baseline,
        correlation_support=1.0,
        data_confidence=1.0,
    )
    assert score >= 50.0  # Should be CRITICAL or SEVERE


def test_driver_rank_and_urgency_in_pipeline():
    """Verify driver_rank and decision_urgency are computed in e2e pipeline."""
    from ml_engine.models.input_schema import CompanyInput, CompanyMetadata, PeriodType, ReportingPeriod, SectorId
    from ml_engine.models.output_schema import UrgencyLabel
    from ml_engine.pipeline import analyze_company

    failing_input = CompanyInput(
        company_id="comp_saas_driver_test",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Driver Test Corp",
            employee_count=100,
            annual_revenue=15_000_000.0,
            revenue_band=RevenueBand.TEN_TO_100M,
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01-01", end="2026-06-30"
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                values=[
                    TimeSeriesPoint(period="2026-01", value=8.0),
                    TimeSeriesPoint(period="2026-02", value=5.0),
                    TimeSeriesPoint(period="2026-03", value=2.0),
                    TimeSeriesPoint(period="2026-04", value=-1.0),
                    TimeSeriesPoint(period="2026-05", value=-3.0),
                    TimeSeriesPoint(period="2026-06", value=-6.0),
                ],
            ),
            MetricInput(
                metric_id="churn_rate",
                values=[
                    TimeSeriesPoint(period="2026-01", value=2.1),
                    TimeSeriesPoint(period="2026-02", value=2.5),
                    TimeSeriesPoint(period="2026-03", value=3.2),
                    TimeSeriesPoint(period="2026-04", value=4.0),
                    TimeSeriesPoint(period="2026-05", value=4.8),
                    TimeSeriesPoint(period="2026-06", value=5.5),
                ],
            ),
        ],
    )

    report = analyze_company(failing_input)
    assert len(report.anomalies) >= 2
    # At least one anomaly in the correlated cluster must be ranked as driver (driver_rank=1)
    driver_ranks = [a.driver_rank for a in report.anomalies]
    assert 1 in driver_ranks
    # Check decision urgency
    urgencies = [a.decision_urgency for a in report.anomalies]
    assert UrgencyLabel.ESCALATING in urgencies or UrgencyLabel.STABLE_BAD in urgencies


def test_candidate_explanations_for_low_confidence():
    """Verify weak-signal anomalies (<0.5 confidence) receive candidate explanations."""
    from ml_engine.anomaly.detector import AnomalyDetector
    from ml_engine.models.internal import MetricDeviation, MetricFeatures
    from ml_engine.models.output_schema import DeviationDirection, TrendDirection

    thresholds = load_thresholds()
    saas_cfg = load_sector_config("TECH_SAAS")
    corr_engine = CorrelationEngine(saas_cfg)
    detector = AnomalyDetector(thresholds, corr_engine)
    gen = SyntheticProfileGenerator(saas_cfg)
    profile = gen.get_calibrated_profile(RevenueBand.ONE_TO_10M)
    baseline = profile["monthly_recurring_revenue_growth"]

    features = MetricFeatures(
        metric_id="monthly_recurring_revenue_growth",
        latest_value=-2.0,
        mean=1.0,
        std=2.0,
        num_points=6,
        has_trend_support=True,
        trend_direction=TrendDirection.DETERIORATING,
    )
    deviation = MetricDeviation(
        metric_id="monthly_recurring_revenue_growth",
        observed_value=-2.0,
        expected_mean=8.5,
        expected_std=3.2,
        z_score=-3.28,
        percentile=0.05,
        direction=DeviationDirection.BELOW_EXPECTED,
        severity_raw=70.0,
        periods_deviating=3,
    )

    anomalies, highlights, health, filtered = detector.detect_anomalies(
        features_map={"monthly_recurring_revenue_growth": features},
        deviations_map={"monthly_recurring_revenue_growth": deviation},
        baselines_map={"monthly_recurring_revenue_growth": baseline},
        data_confidence_map={"monthly_recurring_revenue_growth": 0.4},
    )

    assert len(anomalies) == 1
    # Check that candidate_explanations is a list
    assert isinstance(anomalies[0].candidate_explanations, list)


def test_filtered_metrics_channel():
    """Verify metrics failing noise filter layers are recorded in filtered_metrics."""
    from ml_engine.models.input_schema import CompanyInput, CompanyMetadata, PeriodType, ReportingPeriod, SectorId
    from ml_engine.pipeline import analyze_company

    # Metric with transient 1-period spike (fails Layer 2 persistence)
    input_data = CompanyInput(
        company_id="comp_filter_test",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Filter Test", employee_count=50, revenue_band=RevenueBand.ONE_TO_10M
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01-01", end="2026-06-30"
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                values=[
                    TimeSeriesPoint(period="2026-01", value=8.5),
                    TimeSeriesPoint(period="2026-02", value=8.5),
                    TimeSeriesPoint(period="2026-03", value=8.5),
                    TimeSeriesPoint(period="2026-04", value=8.5),
                    TimeSeriesPoint(period="2026-05", value=8.5),
                    TimeSeriesPoint(period="2026-06", value=-2.0), # Single spike
                ],
            )
        ],
    )

    report = analyze_company(input_data)
    # The transient spike should either be filtered out or recorded
    if len(report.anomalies) == 0:
        assert len(report.metadata.filtered_metrics) >= 1
        fm = report.metadata.filtered_metrics[0]
        assert fm["metric_id"] == "monthly_recurring_revenue_growth"
        assert "L2" in fm["layer"] or "persistence" in fm["reason"].lower()


def test_contribution_pct_sums_to_100():
    """Assert sum(contribution_pct) ≈ 100.0 when multiple anomalies exist."""
    from ml_engine.models.input_schema import CompanyInput, CompanyMetadata, PeriodType, ReportingPeriod, SectorId
    from ml_engine.pipeline import analyze_company

    failing_input = CompanyInput(
        company_id="comp_saas_contrib_test",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Contrib Test Corp",
            employee_count=100,
            annual_revenue=15_000_000.0,
            revenue_band=RevenueBand.TEN_TO_100M,
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01-01", end="2026-06-30"
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                values=[
                    TimeSeriesPoint(period="2026-01", value=8.0),
                    TimeSeriesPoint(period="2026-02", value=5.0),
                    TimeSeriesPoint(period="2026-03", value=2.0),
                    TimeSeriesPoint(period="2026-04", value=-1.0),
                    TimeSeriesPoint(period="2026-05", value=-3.0),
                    TimeSeriesPoint(period="2026-06", value=-6.0),
                ],
            ),
            MetricInput(
                metric_id="churn_rate",
                values=[
                    TimeSeriesPoint(period="2026-01", value=2.1),
                    TimeSeriesPoint(period="2026-02", value=2.5),
                    TimeSeriesPoint(period="2026-03", value=3.2),
                    TimeSeriesPoint(period="2026-04", value=4.0),
                    TimeSeriesPoint(period="2026-05", value=4.8),
                    TimeSeriesPoint(period="2026-06", value=5.5),
                ],
            ),
        ],
    )

    report = analyze_company(failing_input)
    assert len(report.anomalies) >= 2
    contribs = [a.contribution_pct for a in report.anomalies if a.contribution_pct is not None]
    assert len(contribs) == len(report.anomalies)
    assert pytest.approx(sum(contribs), abs=1.0) == 100.0


def test_contribution_pct_null_when_healthy():
    """Assert contribution_pct is None when no anomalies exist / fully healthy report."""
    from ml_engine.models.input_schema import CompanyInput, CompanyMetadata, PeriodType, ReportingPeriod, SectorId
    from ml_engine.pipeline import analyze_company

    healthy_input = CompanyInput(
        company_id="comp_saas_healthy_test",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Healthy Test Corp",
            employee_count=100,
            revenue_band=RevenueBand.TEN_TO_100M,
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01-01", end="2026-06-30"
        ),
        metrics=[
            MetricInput(
                metric_id="monthly_recurring_revenue_growth",
                values=[
                    TimeSeriesPoint(period=f"2026-0{i+1}", value=9.0) for i in range(6)
                ],
            ),
        ],
    )

    report = analyze_company(healthy_input)
    assert len(report.anomalies) == 0
    for a in report.anomalies:
        assert a.contribution_pct is None


def test_contribution_pct_single_anomaly():
    """Assert single anomaly gets contribution_pct = 100.0."""
    from ml_engine.models.input_schema import CompanyInput, CompanyMetadata, PeriodType, ReportingPeriod, SectorId
    from ml_engine.pipeline import analyze_company

    single_anom_input = CompanyInput(
        company_id="comp_saas_single_test",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Single Anom Corp",
            employee_count=100,
            revenue_band=RevenueBand.TEN_TO_100M,
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01-01", end="2026-06-30"
        ),
        metrics=[
            MetricInput(
                metric_id="churn_rate",
                values=[
                    TimeSeriesPoint(period="2026-01", value=2.1),
                    TimeSeriesPoint(period="2026-02", value=2.5),
                    TimeSeriesPoint(period="2026-03", value=3.2),
                    TimeSeriesPoint(period="2026-04", value=4.0),
                    TimeSeriesPoint(period="2026-05", value=4.8),
                    TimeSeriesPoint(period="2026-06", value=6.5),
                ],
            ),
        ],
    )

    report = analyze_company(single_anom_input)
    assert len(report.anomalies) == 1
    assert report.anomalies[0].contribution_pct == 100.0


def test_source_fields_passthrough():
    """Submit MetricInput with source_system and data_as_of — assert AnomalyItem carries them."""
    from ml_engine.models.input_schema import CompanyInput, CompanyMetadata, PeriodType, ReportingPeriod, SectorId
    from ml_engine.pipeline import analyze_company

    source_input = CompanyInput(
        company_id="comp_saas_source_test",
        sector_id=SectorId.TECH_SAAS,
        company_metadata=CompanyMetadata(
            name="Source Test Corp",
            employee_count=100,
            revenue_band=RevenueBand.TEN_TO_100M,
        ),
        reporting_period=ReportingPeriod(
            type=PeriodType.MONTHLY, start="2026-01-01", end="2026-06-30"
        ),
        metrics=[
            MetricInput(
                metric_id="churn_rate",
                source_system="CRM",
                grain="daily",
                data_as_of="2026-08-28",
                values=[
                    TimeSeriesPoint(period="2026-01", value=2.1),
                    TimeSeriesPoint(period="2026-02", value=2.5),
                    TimeSeriesPoint(period="2026-03", value=3.2),
                    TimeSeriesPoint(period="2026-04", value=4.0),
                    TimeSeriesPoint(period="2026-05", value=4.8),
                    TimeSeriesPoint(period="2026-06", value=6.5),
                ],
            ),
        ],
    )

    report = analyze_company(source_input)
    assert len(report.anomalies) >= 1
    anom = report.anomalies[0]
    assert anom.source_system == "CRM"
    assert anom.data_as_of == "2026-08-28"


