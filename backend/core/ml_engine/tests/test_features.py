"""Tests for feature extraction, trend analysis, and normalization."""

import pytest
from ml_engine.config.loader import load_sector_config
from ml_engine.config.schema import OptimizationDirection
from ml_engine.features.extractor import FeatureExtractor
from ml_engine.features.normalizer import FeatureNormalizer
from ml_engine.features.ratios import RatioCalculator
from ml_engine.models.input_schema import MetricInput, PeriodType, RevenueBand, TimeSeriesPoint
from ml_engine.models.output_schema import DeviationDirection, TrendDirection
from ml_engine.synthetic.generator import SyntheticProfileGenerator


def test_feature_extractor_sufficient_points():
    """Verify slope and acceleration computation with >= 6 points."""
    extractor = FeatureExtractor(min_periods_for_trend=6)
    metric_input = MetricInput(
        metric_id="test_growth",
        values=[
            TimeSeriesPoint(period="2026-01", value=10.0),
            TimeSeriesPoint(period="2026-02", value=8.0),
            TimeSeriesPoint(period="2026-03", value=6.0),
            TimeSeriesPoint(period="2026-04", value=4.0),
            TimeSeriesPoint(period="2026-05", value=2.0),
            TimeSeriesPoint(period="2026-06", value=0.0),
        ],
    )
    features = extractor.extract_features(metric_input)
    assert features.has_trend_support is True
    assert features.slope is not None
    assert features.slope == pytest.approx(-2.0, 0.01)
    assert features.trend_direction == TrendDirection.DETERIORATING


def test_feature_extractor_insufficient_points():
    """Verify slope and acceleration return None when < 6 points."""
    extractor = FeatureExtractor(min_periods_for_trend=6)
    metric_input = MetricInput(
        metric_id="test_growth",
        values=[
            TimeSeriesPoint(period="2026-01", value=10.0),
            TimeSeriesPoint(period="2026-02", value=8.0),
            TimeSeriesPoint(period="2026-03", value=6.0),
        ],
    )
    features = extractor.extract_features(metric_input)
    assert features.has_trend_support is False
    assert features.slope is None
    assert features.acceleration is None


def test_feature_normalizer():
    """Verify normalization against synthetic profile."""
    saas_cfg = load_sector_config("TECH_SAAS")
    gen = SyntheticProfileGenerator(saas_cfg)
    profile = gen.get_calibrated_profile(RevenueBand.ONE_TO_10M)
    baseline = profile["monthly_recurring_revenue_growth"]

    extractor = FeatureExtractor(min_periods_for_trend=6)
    metric_input = MetricInput(
        metric_id="monthly_recurring_revenue_growth",
        values=[
            TimeSeriesPoint(period="2026-01", value=8.0),
            TimeSeriesPoint(period="2026-02", value=6.0),
            TimeSeriesPoint(period="2026-03", value=4.0),
            TimeSeriesPoint(period="2026-04", value=2.0),
            TimeSeriesPoint(period="2026-05", value=0.0),
            TimeSeriesPoint(period="2026-06", value=-2.0),
        ],
    )
    features = extractor.extract_features(metric_input, baseline.metric_def)
    normalizer = FeatureNormalizer(z_threshold_flag=1.5)
    deviation = normalizer.normalize(features, baseline)

    assert deviation.observed_value == -2.0
    assert deviation.z_score < -2.0  # Below baseline mean of ~8.5
    assert deviation.direction == DeviationDirection.BELOW_EXPECTED
    assert deviation.periods_deviating >= 2


def test_ratio_calculator():
    """Verify cross-metric ratio computations."""
    ltv_cac = RatioCalculator.compute_ltv_cac(ltv=30000.0, cac=6000.0)
    assert ltv_cac == 5.0

    rev_emp = RatioCalculator.compute_revenue_per_employee(annual_revenue=10000000.0, employee_count=50)
    assert rev_emp == 200000.0
