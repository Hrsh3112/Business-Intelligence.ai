"""Tests for Beta-Binomial feedback Bayesian recalibration module."""

import json
from pathlib import Path
import pytest
from ml_engine.config.feedback_recalibrator import (
    BASE_THRESHOLD,
    MAX_ADJUSTMENT,
    build_threshold_map,
    compute_adjusted_threshold,
)


def test_cold_start_returns_base_threshold(tmp_path: Path):
    """When feedback log does not exist or has < 5 entries, returns base threshold."""
    non_existent = tmp_path / "non_existent.jsonl"
    assert compute_adjusted_threshold("tech_saas", "churn_rate", non_existent) == BASE_THRESHOLD

    # Log with 3 entries (< 5 cold start threshold)
    log_file = tmp_path / "feedback_short.jsonl"
    with open(log_file, "w") as f:
        for _ in range(3):
            f.write(json.dumps({"sector": "tech_saas", "metric_id": "churn_rate", "rating": "not_useful"}) + "\n")

    assert compute_adjusted_threshold("tech_saas", "churn_rate", log_file) == BASE_THRESHOLD


def test_all_useful_feedback_lowers_noise_rate(tmp_path: Path):
    """10 'useful' feedback entries should result in a low noise rate and threshold close to base."""
    log_file = tmp_path / "feedback_useful.jsonl"
    with open(log_file, "w") as f:
        for _ in range(10):
            f.write(json.dumps({"sector": "tech_saas", "metric_id": "churn_rate", "rating": "useful"}) + "\n")

    # Positives = 1 (prior) + 10 = 11, Negatives = 1 (prior) + 0 = 1
    # noise_rate = 1 / 12 = 0.0833
    # adjusted = 1.5 + 0.0833 * 0.8 = 1.5667 -> 1.57
    thresh = compute_adjusted_threshold("tech_saas", "churn_rate", log_file)
    assert 1.50 <= thresh <= 1.60


def test_all_noise_feedback_raises_threshold(tmp_path: Path):
    """10 'not_useful' feedback entries should raise the threshold substantially."""
    log_file = tmp_path / "feedback_noise.jsonl"
    with open(log_file, "w") as f:
        for _ in range(10):
            f.write(json.dumps({"sector": "tech_saas", "metric_id": "churn_rate", "rating": "not_useful"}) + "\n")

    # Positives = 1, Negatives = 11 -> noise_rate = 11/12 = 0.9167
    # adjusted = 1.5 + 0.9167 * 0.8 = 2.233 -> 2.23
    thresh = compute_adjusted_threshold("tech_saas", "churn_rate", log_file)
    assert thresh >= 2.15


def test_threshold_capped_at_max(tmp_path: Path):
    """Extreme noise feedback should never exceed BASE + MAX_ADJUSTMENT."""
    log_file = tmp_path / "feedback_extreme.jsonl"
    with open(log_file, "w") as f:
        for _ in range(100):
            f.write(json.dumps({"sector": "tech_saas", "metric_id": "churn_rate", "rating": "not_useful"}) + "\n")

    thresh = compute_adjusted_threshold("tech_saas", "churn_rate", log_file)
    assert thresh <= round(BASE_THRESHOLD + MAX_ADJUSTMENT, 2)


def test_threshold_map_filters_by_sector_and_metric(tmp_path: Path):
    """Threshold map properly matches by sector and metric_id."""
    log_file = tmp_path / "feedback_mixed.jsonl"
    with open(log_file, "w") as f:
        # 10 not_useful for tech_saas churn_rate
        for _ in range(10):
            f.write(json.dumps({"sector": "tech_saas", "metric_id": "churn_rate", "rating": "not_useful"}) + "\n")
        # 10 not_useful for fintech nrr (different sector)
        for _ in range(10):
            f.write(json.dumps({"sector": "fintech", "metric_id": "net_revenue_retention", "rating": "not_useful"}) + "\n")

    tmap = build_threshold_map("tech_saas", ["churn_rate", "net_revenue_retention"], log_file)
    assert tmap["churn_rate"] > BASE_THRESHOLD
    # net_revenue_retention in tech_saas has 0 feedback entries -> base threshold
    assert tmap["net_revenue_retention"] == BASE_THRESHOLD
