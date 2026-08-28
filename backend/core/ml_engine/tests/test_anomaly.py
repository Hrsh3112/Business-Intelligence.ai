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
