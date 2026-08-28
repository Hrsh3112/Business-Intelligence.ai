"""Composite severity scoring for confirmed anomalies."""

from typing import Dict, Optional
import numpy as np

from ..config.schema import ThresholdsConfig
from ..models.internal import MetricDeviation, MetricFeatures
from ..synthetic.generator import CalibratedMetricBaseline


class SeverityScorer:
    """Computes composite 0-100 severity scores for detected anomalies."""

    def __init__(self, thresholds: ThresholdsConfig):
        self.thresholds = thresholds
        self.weights = thresholds.weights

    def compute_score(
        self,
        features: MetricFeatures,
        deviation: MetricDeviation,
        baseline: CalibratedMetricBaseline,
        correlation_support: float = 0.0,
        data_confidence: float = 1.0
    ) -> float:
        """Calculate composite severity score from deviation, trend, importance, and support."""
        w = self.weights

        # 1. Magnitude Score (0-30 pts): distance in std deviations
        mag_ratio = min(abs(deviation.z_score) / 4.0, 1.0)
        magnitude_score = mag_ratio * w.get("magnitude", 30.0)

        # 2. Persistence Score (0-20 pts): length of consecutive deviating periods
        pers_count = deviation.periods_deviating if features.has_trend_support else (2 if abs(deviation.z_score) >= 2.5 else 1)
        pers_ratio = min(pers_count / 6.0, 1.0)
        persistence_score = pers_ratio * w.get("persistence", 20.0)

        # 3. Trajectory Score (0-20 pts): velocity of worsening
        slope_val = abs(features.slope) if (features.has_trend_support and features.slope is not None) else 0.0
        # Normalize slope against std dev
        rel_slope = slope_val / baseline.std if baseline.std > 0 else slope_val
        traj_ratio = min(rel_slope / 0.5, 1.0)
        trajectory_score = traj_ratio * w.get("trajectory", 20.0)

        # 4. Importance Score (0-15 pts): metric weight in sector
        importance_ratio = min(baseline.weight, 1.0)
        importance_score = importance_ratio * w.get("importance", 15.0)

        # 5. Correlation Support Score (0-15 pts): confirmation from related metrics
        support_ratio = min(correlation_support, 1.0)
        support_score = support_ratio * w.get("support", 15.0)

        raw_total = magnitude_score + persistence_score + trajectory_score + importance_score + support_score

        # Factor in input data confidence (0.0 to 1.0)
        # Full confidence (1.0) retains 100% of score, low confidence (0.4) moderates severity slightly
        confidence_factor = 0.75 + (0.25 * float(np.clip(data_confidence, 0.0, 1.0)))
        adjusted_score = raw_total * confidence_factor

        return round(float(np.clip(adjusted_score, 0.0, 100.0)), 1)
