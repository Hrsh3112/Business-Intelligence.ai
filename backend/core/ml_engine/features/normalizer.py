"""Normalization and comparison against synthetic baselines."""

from typing import Dict, List, Optional
import numpy as np

from ..config.schema import OptimizationDirection
from ..models.internal import MetricDeviation, MetricFeatures
from ..models.output_schema import DeviationDirection
from ..synthetic.distributions import compute_percentile, compute_z_score
from ..synthetic.generator import CalibratedMetricBaseline


class FeatureNormalizer:
    """Computes z-scores, percentiles, and deviation vectors against synthetic baselines."""

    def __init__(self, z_threshold_flag: float = 1.5):
        self.z_threshold_flag = z_threshold_flag

    def normalize(
        self,
        features: MetricFeatures,
        baseline: CalibratedMetricBaseline
    ) -> MetricDeviation:
        """Compare observed features against calibrated synthetic baseline."""
        latest_val = features.latest_value
        exp_mean = baseline.mean
        exp_std = baseline.std

        z = compute_z_score(latest_val, exp_mean, exp_std)
        pct = compute_percentile(latest_val, exp_mean, exp_std)

        # Deviation direction
        direction_mode = baseline.direction
        if np.isclose(latest_val, exp_mean, atol=1e-5):
            dev_direction = DeviationDirection.AS_EXPECTED
        elif latest_val > exp_mean:
            dev_direction = DeviationDirection.ABOVE_EXPECTED
        else:
            dev_direction = DeviationDirection.BELOW_EXPECTED

        # Historical z-scores
        historical_z = []
        consecutive_deviating = 0
        trailing_deviating_count = 0

        for item in features.values_with_periods:
            val = item["value"]
            period = item["period"]
            pt_z = compute_z_score(val, exp_mean, exp_std)
            historical_z.append({
                "period": period,
                "value": val,
                "z_score": round(pt_z, 3),
            })

        # Calculate trailing consecutive deviating periods (only if trend support is valid)
        if features.has_trend_support:
            for item in reversed(historical_z):
                if abs(item["z_score"]) >= self.z_threshold_flag:
                    trailing_deviating_count += 1
                else:
                    break
        else:
            trailing_deviating_count = 0

        return MetricDeviation(
            metric_id=features.metric_id,
            observed_value=latest_val,
            expected_mean=exp_mean,
            expected_std=exp_std,
            z_score=round(z, 3),
            percentile=round(pct, 2),
            direction=dev_direction,
            severity_raw=round(abs(z), 3),
            historical_z_scores=historical_z,
            periods_deviating=trailing_deviating_count,
        )
