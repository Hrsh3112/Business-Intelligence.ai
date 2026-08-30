import os
from pathlib import Path
from typing import Dict, List, Optional, Set
import numpy as np

from ..config.feedback_recalibrator import build_threshold_map
from ..config.schema import OptimizationDirection, ThresholdsConfig
from ..models.internal import FilterResult, MetricDeviation, MetricFeatures
from ..synthetic.correlations import CorrelationEngine
from ..synthetic.generator import CalibratedMetricBaseline
from .isolation_forest_layer import build_metric_matrix, run_isolation_forest


class MultiLayerNoiseFilter:
    """Applies a 4-layer sieve to distinguish true structural anomalies from statistical noise."""

    def __init__(
        self,
        thresholds: ThresholdsConfig,
        correlation_engine: CorrelationEngine,
        sector_id: Optional[str] = None,
        feedback_log_path: Optional[Path] = None,
        metric_ids: Optional[List[str]] = None,
    ):
        self.thresholds = thresholds
        self.correlation_engine = correlation_engine
        self.sector_id = sector_id
        self.feedback_log_path = feedback_log_path

        if sector_id and metric_ids:
            self.thresholds_map = build_threshold_map(
                sector=sector_id,
                metric_ids=metric_ids,
                feedback_log=feedback_log_path,
            )
        else:
            self.thresholds_map = {}

    def run_l1b_pass(self, all_metric_values: Dict[str, List[float]]) -> Set[str]:
        """Run Isolation Forest multivariate anomaly detection across metrics.

        Returns the set of metric IDs contributing to multivariate anomalies if flagged.
        Controlled by USE_ISOLATION_FOREST environment variable (defaults to True if set or True).
        """
        use_if = os.getenv("USE_ISOLATION_FOREST", "true").lower() in ("true", "1", "yes")
        if not use_if or not all_metric_values or len(all_metric_values) < 2:
            return set()

        matrix = build_metric_matrix(all_metric_values)
        if matrix.shape[0] < 8 or matrix.shape[1] < 2:
            return set()

        flags = run_isolation_forest(matrix)
        # If the latest period is flagged as multivariate outlier:
        if len(flags) > 0 and bool(flags[-1]):
            return set(all_metric_values.keys())
        return set()

    def filter_metric(
        self,
        features: MetricFeatures,
        deviation: MetricDeviation,
        baseline: CalibratedMetricBaseline,
        all_deviations: Dict[str, MetricDeviation],
        multivariate_flagged: bool = False,
    ) -> FilterResult:
        """Apply 4 filtering layers to the metric deviation."""
        abs_z = abs(deviation.z_score)

        # Layer 1: Statistical Threshold (with Bayesian Recalibration + L1b Multivariate)
        effective_threshold = self.thresholds_map.get(
            baseline.metric_id, self.thresholds.z_threshold_flag
        )
        l1_passed = (abs_z >= effective_threshold) or multivariate_flagged

        if not l1_passed:
            is_recalibrated = (
                baseline.metric_id in self.thresholds_map
                and self.thresholds_map[baseline.metric_id] != self.thresholds.z_threshold_flag
            )
            failed_layer_label = "L1_recalibrated" if is_recalibrated else "L1"
            return FilterResult(
                passed=False,
                l1_passed=False,
                l2_passed=False,
                l3_passed=False,
                l4_passed=False,
                noise_confidence=0.1,
                rejection_reason=f"Deviation (|z|={abs_z:.2f}) is below flag threshold ({effective_threshold:.2f})",
                layer_failed=failed_layer_label,
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
                rejection_reason="Deviation lacks persistence across consecutive periods (transient spike)",
                layer_failed="L2",
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
                rejection_reason="Deviation falls within expected seasonal cycle variation",
                layer_failed="L4",
            )

        if not l3_passed:
            return FilterResult(
                passed=False,
                l1_passed=True,
                l2_passed=True,
                l3_passed=False,
                l4_passed=l4_passed,
                noise_confidence=0.35,
                rejection_reason="Deviation is contradicted by strong opposite movements in correlated metrics",
                layer_failed="L3",
                correlated_metric_ids=confirming_correlations,
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
            layer_failed=None,
            correlated_metric_ids=confirming_correlations,
        )
