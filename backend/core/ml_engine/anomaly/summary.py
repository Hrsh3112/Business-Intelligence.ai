"""Deterministic natural language summary generation for detected anomalies."""

from ..config.schema import OptimizationDirection
from ..models.internal import MetricDeviation, MetricFeatures
from ..models.output_schema import DeviationDirection, TrendDirection
from ..synthetic.generator import CalibratedMetricBaseline


class AnomalySummaryGenerator:
    """Generates concise, human-readable executive summaries for anomalies."""

    @staticmethod
    def generate_summary(
        features: MetricFeatures,
        deviation: MetricDeviation,
        baseline: CalibratedMetricBaseline
    ) -> str:
        """Construct a deterministic natural language summary without external LLM calls."""
        metric_name = baseline.display_name
        current_val = deviation.observed_value
        expected_val = deviation.expected_mean
        z = deviation.z_score
        abs_z = abs(z)
        rel_pos = "below" if z < 0 else "above"

        # Format numbers cleanly
        def fmt(v: float) -> str:
            if abs(v) >= 1000:
                return f"{v:,.0f}"
            elif abs(v) >= 10:
                return f"{v:.1f}"
            else:
                return f"{v:.2f}"

        # If time series is available and has >= 6 periods
        if features.has_trend_support and len(features.values_with_periods) >= 2:
            start_val = features.values_with_periods[0]["value"]
            n_periods = features.num_points
            
            if start_val < current_val:
                movement = f"risen from {fmt(start_val)} to {fmt(current_val)}"
            elif start_val > current_val:
                movement = f"declined from {fmt(start_val)} to {fmt(current_val)}"
            else:
                movement = f"remained flat at {fmt(current_val)}"

            summary = (
                f"{metric_name} has {movement} over {n_periods} periods, "
                f"now {abs_z:.2f} standard deviations {rel_pos} the expected baseline for a company of this profile ({fmt(expected_val)})."
            )

            if features.trend_direction == TrendDirection.DETERIORATING:
                if features.acceleration is not None and abs(features.acceleration) > 0.05:
                    summary += " The negative trend is accelerating."
                else:
                    summary += " Trajectory is deteriorating."
            elif features.trend_direction == TrendDirection.IMPROVING:
                summary += " Trajectory is showing signs of recovery."
        else:
            # Single-point or short series summary
            summary = (
                f"{metric_name} is currently {fmt(current_val)}, which is {abs_z:.2f} "
                f"standard deviations {rel_pos} the expected baseline of {fmt(expected_val)}."
            )

        return summary
