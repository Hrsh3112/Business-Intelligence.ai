"""Multi-layer noise filtering for structural anomaly identification."""

from typing import Dict, List, Optional
import numpy as np

from ..config.schema import OptimizationDirection, ThresholdsConfig
from ..models.internal import FilterResult, MetricDeviation, MetricFeatures
from ..synthetic.correlations import CorrelationEngine
from ..synthetic.generator import CalibratedMetricBaseline


class MultiLayerNoiseFilter:
    """Applies a 4-layer sieve to distinguish true structural anomalies from statistical noise."""

    def __init__(
        self,
        thresholds: ThresholdsConfig,
        correlation_engine: CorrelationEngine
    ):
        self.thresholds = thresholds
        self.correlation_engine = correlation_engine

    def filter_metric(
        self,
        features: MetricFeatures,
        deviation: MetricDeviation,
        baseline: CalibratedMetricBaseline,
        all_deviations: Dict[str, MetricDeviation]
    ) -> FilterResult:
        """Apply 4 filtering layers to the metric deviation."""
        abs_z = abs(deviation.z_score)

        # Layer 1: Statistical Threshold
        l1_passed = abs_z >= self.thresholds.z_threshold_flag
        if not l1_passed:
            return FilterResult(
                passed=False,
                l1_passed=False,
                l2_passed=False,
                l3_passed=False,
                l4_passed=False,
                noise_confidence=0.1,
                rejection_reason=f"Deviation (|z|={abs_z:.2f}) is below flag threshold ({self.thresholds.z_threshold_flag})"
            )

        # Layer 2: Persistence Filter
        # If trend support is present, check consecutive periods deviating
        if features.has_trend_support:
            l2_passed = deviation.periods_deviating >= self.thresholds.min_persistence_periods
        else:
            # Below 6 periods: only allow if strong alert (|z| >= z_threshold_alert)
            l2_passed = abs_z >= self.thresholds.z_threshold_alert

        if not l2_passed:
            return FilterResult(
                passed=False,
                l1_passed=True,
                l2_passed=False,
                l3_passed=False,
                l4_passed=False,
                noise_confidence=0.35,
                rejection_reason="Deviation lacks persistence across consecutive periods (transient spike)"
            )

        # Layer 3: Correlation Consistency
        correlated_metric_ids = self.correlation_engine.get_correlated_metrics(
            baseline.metric_id,
            threshold=self.thresholds.correlation_threshold
        )

        confirming_correlations = []
        conflicting_correlations = []

        for other_id in correlated_metric_ids:
            if other_id in all_deviations:
                other_dev = all_deviations[other_id]
                corr = self.correlation_engine.get_correlation(baseline.metric_id, other_id)
                # Expected co-deviation product: sign(z1 * z2 * corr) should be positive
                co_dev_sign = deviation.z_score * other_dev.z_score * corr
                if co_dev_sign > 0 and abs(other_dev.z_score) >= 1.0:
                    confirming_correlations.append(other_id)
                elif co_dev_sign < -0.5 and abs(other_dev.z_score) >= 1.5:
                    conflicting_correlations.append(other_id)

        # Layer 3 passes unless heavily contradicted by strong opposite movements
        l3_passed = len(conflicting_correlations) == 0

        # Layer 4: Contextual / Seasonality Filter
        l4_passed = True
        if baseline.metric_def.seasonality.enabled:
            seasonal_amp = baseline.metric_def.seasonality.amplitude
            # If deviation is within normal seasonal swing and not an alert
            if abs_z < (self.thresholds.z_threshold_alert) and abs_z * baseline.std <= seasonal_amp:
                l4_passed = False

        if not l4_passed:
            return FilterResult(
                passed=False,
                l1_passed=True,
                l2_passed=True,
                l3_passed=l3_passed,
                l4_passed=False,
                noise_confidence=0.4,
                rejection_reason="Deviation falls within expected seasonal cycle variation"
            )

        # Calculate noise confidence (probability this is true structural signal, 0.0 to 1.0)
        # Base confidence from z-score (0.0 to 0.65)
        base_conf = min(abs_z / 5.0, 0.65)
        # Bonus for persistence (up to +0.20)
        pers_bonus = 0.20 if deviation.periods_deviating >= 3 else (0.10 if deviation.periods_deviating >= 2 else 0.0)
        # Bonus for correlated support (+0.15)
        corr_bonus = 0.15 if len(confirming_correlations) > 0 else 0.0
        # Meaningful penalty for interpolated data (up to -0.30)
        interp_penalty = 0.30 * features.interpolated_ratio

        raw_conf = base_conf + pers_bonus + corr_bonus - interp_penalty
        final_noise_conf = float(np.clip(raw_conf, 0.30, 0.99))

        return FilterResult(
            passed=l1_passed and l2_passed and l3_passed and l4_passed,
            l1_passed=l1_passed,
            l2_passed=l2_passed,
            l3_passed=l3_passed,
            l4_passed=l4_passed,
            noise_confidence=round(final_noise_conf, 2),
            correlated_metric_ids=confirming_correlations,
        )
