"""Tests for Isolation Forest multivariate anomaly detection layer (L1b)."""

import os
import numpy as np
import pytest
from ml_engine.anomaly.isolation_forest_layer import (
    build_metric_matrix,
    run_isolation_forest,
)
from ml_engine.anomaly.noise_filter import MultiLayerNoiseFilter
from ml_engine.config.schema import ThresholdsConfig
from ml_engine.synthetic.correlations import CorrelationEngine
from ml_engine.config.loader import load_sector_config


def test_isolation_forest_returns_bool_array():
    """Valid matrix with 10 periods and 3 metrics should return boolean array of length 10."""
    np.random.seed(42)
    matrix = np.random.normal(loc=10.0, scale=1.0, size=(10, 3))
    flags = run_isolation_forest(matrix, contamination=0.2, random_state=42)
    assert isinstance(flags, np.ndarray)
    assert flags.shape == (10,)
    assert flags.dtype == bool


def test_isolation_forest_skipped_for_single_metric():
    """Matrix with < 2 metrics should return all False without raising."""
    matrix = np.ones((10, 1))
    flags = run_isolation_forest(matrix)
    assert len(flags) == 10
    assert not np.any(flags)


def test_isolation_forest_skipped_for_short_series():
    """Matrix with < 8 periods should return all False without raising."""
    matrix = np.ones((5, 3))
    flags = run_isolation_forest(matrix)
    assert len(flags) == 5
    assert not np.any(flags)


def test_build_metric_matrix_alignment():
    """Matrix builder aligns multiple time series by shortest common length."""
    series_map = {
        "m1": [1.0, 2.0, 3.0, 4.0, 5.0],
        "m2": [10.0, 20.0, 30.0, 40.0],  # length 4
    }
    matrix = build_metric_matrix(series_map)
    assert matrix.shape == (4, 2)
    # The last 4 items of m1 are [2.0, 3.0, 4.0, 5.0]
    assert np.array_equal(matrix[:, 0], [2.0, 3.0, 4.0, 5.0])
    assert np.array_equal(matrix[:, 1], [10.0, 20.0, 30.0, 40.0])


def test_l1b_pass_in_noise_filter():
    """MultiLayerNoiseFilter.run_l1b_pass identifies multivariate anomaly."""
    thresholds = ThresholdsConfig()
    sector_cfg = load_sector_config("tech_saas")
    corr_engine = CorrelationEngine(sector_cfg)
    noise_filter = MultiLayerNoiseFilter(thresholds, corr_engine)

    # 10 periods of normal data, with an outlier at the final period
    np.random.seed(42)
    s1 = list(np.random.normal(10, 0.5, 9)) + [100.0]
    s2 = list(np.random.normal(5, 0.2, 9)) + [50.0]
    series_map = {"churn_rate": s1, "net_revenue_retention": s2}

    flagged = noise_filter.run_l1b_pass(series_map)
    assert "churn_rate" in flagged or len(flagged) >= 2
