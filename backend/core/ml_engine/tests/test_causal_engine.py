"""Tests for Granger causality driver directionality module."""

import numpy as np
import pytest
from ml_engine.anomaly.causal_engine import (
    granger_causes,
    rank_cluster_by_granger,
)
from ml_engine.models.output_schema import (
    AnomalyItem,
    DeviationDetails,
    DeviationDirection,
    SeverityLabel,
    TrendDetails,
    TrendDirection,
)


def _make_dummy_anomaly(metric_id: str, anom_id: str, z_score: float = 2.0) -> AnomalyItem:
    return AnomalyItem(
        anomaly_id=anom_id,
        metric_id=metric_id,
        metric_display_name=metric_id.replace("_", " ").title(),
        category="revenue",
        severity_score=60.0,
        severity_label=SeverityLabel.CRITICAL,
        deviation=DeviationDetails(
            observed_current=10.0,
            expected_value=5.0,
            expected_std=1.0,
            z_score=z_score,
            percentile=95.0,
            direction=DeviationDirection.ABOVE_EXPECTED,
        ),
        trend=TrendDetails(direction=TrendDirection.DETERIORATING),
        noise_confidence=0.9,
        natural_language_summary="Test anomaly",
        driver_rank=0,
    )


def test_granger_causes_known_causal_pair():
    """Series B driven by lagged shocks of series A is Granger-caused by A."""
    np.random.seed(42)
    n = 60
    a = np.random.normal(0, 1, n)
    b = np.zeros(n)
    for t in range(1, n):
        b[t] = 0.1 * b[t - 1] + 0.9 * a[t - 1] + np.random.normal(0, 0.1)

    # A Granger-causes B (p < 0.05)
    assert granger_causes(list(a), list(b), max_lag=2, p_threshold=0.05) is True


def test_granger_causes_independent_series():
    """Two independent random series should not indicate bilateral causality."""
    np.random.seed(123)
    n = 50
    a = list(np.random.normal(0, 1, n))
    b = list(np.random.normal(0, 1, n))
    assert not (granger_causes(a, b) and granger_causes(b, a))


def test_granger_skipped_for_short_series():
    """Series with < 10 periods should return False without raising."""
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [2.0, 4.0, 6.0, 8.0, 10.0]
    assert granger_causes(a, b) is False


def test_rank_cluster_promotes_correct_driver():
    """In a cluster where metric A Granger-causes metric B, A is promoted to driver_rank=1."""
    np.random.seed(42)
    n = 60
    a_vals = np.random.normal(0, 1, n)
    b_vals = np.zeros(n)
    for t in range(1, n):
        b_vals[t] = 0.1 * b_vals[t - 1] + 0.9 * a_vals[t - 1] + np.random.normal(0, 0.1)

    anom_a = _make_dummy_anomaly("metric_a", "anom_001")
    anom_b = _make_dummy_anomaly("metric_b", "anom_002")
    anom_a.correlated_anomalies = ["anom_002"]
    anom_b.correlated_anomalies = ["anom_001"]

    cluster = [anom_a, anom_b]
    series_map = {"metric_a": list(a_vals), "metric_b": list(b_vals)}

    ranked = rank_cluster_by_granger(cluster, series_map)
    a_res = next(x for x in ranked if x.metric_id == "metric_a")
    b_res = next(x for x in ranked if x.metric_id == "metric_b")

    assert a_res.driver_rank == 1
    assert b_res.driver_rank == 0
    assert a_res.granger_tested is True
    assert b_res.granger_tested is True


def test_rank_cluster_falls_back_when_inconclusive():
    """When no causal edge is found, cluster driver_ranks are unchanged."""
    anom_a = _make_dummy_anomaly("m1", "anom_001")
    anom_b = _make_dummy_anomaly("m2", "anom_002")
    anom_a.driver_rank = 0
    anom_b.driver_rank = 0

    # Constant series (zero variance -> no causality)
    series_map = {"m1": [5.0] * 15, "m2": [10.0] * 15}
    ranked = rank_cluster_by_granger([anom_a, anom_b], series_map)

    assert ranked[0].driver_rank == 0
    assert ranked[1].driver_rank == 0
