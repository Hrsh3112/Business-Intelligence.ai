"""Feature extraction engine for time-series metrics."""

from typing import Dict, List, Optional, Union
import numpy as np

from ..config.schema import MetricDefinition, OptimizationDirection
from ..models.input_schema import MetricInput
from ..models.internal import MetricFeatures
from ..models.output_schema import TrendDirection


class FeatureExtractor:
    """Extracts level, trend, volatility, and acceleration features from metric inputs."""

    def __init__(self, min_periods_for_trend: Union[Dict[str, int], int] = 6):
        self.min_periods_for_trend = min_periods_for_trend

    def extract_features(
        self,
        metric_input: MetricInput,
        metric_def: Optional[MetricDefinition] = None
    ) -> MetricFeatures:
        """Extract statistical and time-series features from raw metric series."""
        points = metric_input.values
        num_points = len(points)
        raw_values = np.array([p.value for p in points], dtype=np.float64)
        interpolated_flags = np.array([p.interpolated for p in points], dtype=bool)

        latest_value = float(raw_values[-1])
        mean_val = float(np.mean(raw_values))
        std_val = float(np.std(raw_values, ddof=1)) if num_points > 1 else 0.0
        interpolated_ratio = float(np.mean(interpolated_flags))

        values_with_periods = [
            {"period": p.period, "value": p.value, "interpolated": float(p.interpolated)}
            for p in points
        ]

        if isinstance(self.min_periods_for_trend, dict):
            gran = metric_input.granularity.value.lower() if hasattr(metric_input.granularity, "value") else str(metric_input.granularity).lower()
            min_req = self.min_periods_for_trend.get(gran, 6)
        else:
            min_req = int(self.min_periods_for_trend)

        # Check minimum periods threshold
        if num_points < min_req:
            return MetricFeatures(
                metric_id=metric_input.metric_id,
                latest_value=latest_value,
                mean=mean_val,
                std=std_val,
                slope=None,
                acceleration=None,
                volatility=std_val,
                num_points=num_points,
                interpolated_ratio=interpolated_ratio,
                has_trend_support=False,
                trend_direction=TrendDirection.STABLE,
                values_with_periods=values_with_periods,
            )

        # Sufficient data (>= 6 periods) -> compute slope & acceleration
        x = np.arange(num_points, dtype=np.float64)
        # Down-weight interpolated points: weight 0.5 vs 1.0
        weights = np.where(interpolated_flags, 0.5, 1.0)

        # Weighted least-squares linear fit
        try:
            poly_fit = np.polyfit(x, raw_values, deg=1, w=weights)
            slope = float(poly_fit[0])
        except Exception:
            slope = 0.0

        # Acceleration: second derivative via quadratic fit
        try:
            quad_fit = np.polyfit(x, raw_values, deg=2, w=weights)
            # Quadratic is a*x^2 + b*x + c, 2nd derivative is 2*a
            acceleration = float(2.0 * quad_fit[0])
        except Exception:
            acceleration = 0.0

        # Determine trend direction (health impact)
        direction_mode = (
            metric_def.direction if metric_def else OptimizationDirection.HIGHER_IS_BETTER
        )

        slope_threshold = 0.05
        # Scale slope threshold relative to standard deviation if non-zero
        if std_val > 1e-4:
            rel_slope = slope / std_val
        else:
            rel_slope = slope

        if direction_mode == OptimizationDirection.HIGHER_IS_BETTER:
            if rel_slope > slope_threshold:
                trend_direction = TrendDirection.IMPROVING
            elif rel_slope < -slope_threshold:
                trend_direction = TrendDirection.DETERIORATING
            else:
                trend_direction = TrendDirection.STABLE
        elif direction_mode == OptimizationDirection.LOWER_IS_BETTER:
            if rel_slope < -slope_threshold:
                trend_direction = TrendDirection.IMPROVING
            elif rel_slope > slope_threshold:
                trend_direction = TrendDirection.DETERIORATING
            else:
                trend_direction = TrendDirection.STABLE
        else:
            trend_direction = TrendDirection.STABLE

        return MetricFeatures(
            metric_id=metric_input.metric_id,
            latest_value=latest_value,
            mean=mean_val,
            std=std_val,
            slope=round(slope, 4),
            acceleration=round(acceleration, 4),
            volatility=round(std_val, 4),
            num_points=num_points,
            interpolated_ratio=interpolated_ratio,
            has_trend_support=True,
            trend_direction=trend_direction,
            values_with_periods=values_with_periods,
        )
