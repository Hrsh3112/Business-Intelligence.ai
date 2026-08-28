"""Core anomaly detection and health assessment orchestrator."""

from typing import Dict, List, Tuple
import numpy as np

from ..config.schema import OptimizationDirection, ThresholdsConfig
from ..models.internal import MetricDeviation, MetricFeatures
from ..models.output_schema import (
    AnomalyItem,
    DeviationDetails,
    HighlightItem,
    TrendDetails,
    TrendPoint,
)
from ..synthetic.correlations import CorrelationEngine
from ..synthetic.generator import CalibratedMetricBaseline
from .classifier import SeverityClassifier
from .noise_filter import MultiLayerNoiseFilter
from .scorer import SeverityScorer
from .summary import AnomalySummaryGenerator


class AnomalyDetector:
    """Orchestrates multi-layer noise filtering, severity scoring, and report item assembly."""

    def __init__(
        self,
        thresholds: ThresholdsConfig,
        correlation_engine: CorrelationEngine
    ):
        self.thresholds = thresholds
        self.noise_filter = MultiLayerNoiseFilter(thresholds, correlation_engine)
        self.scorer = SeverityScorer(thresholds)
        self.classifier = SeverityClassifier(thresholds)

    def detect_anomalies(
        self,
        features_map: Dict[str, MetricFeatures],
        deviations_map: Dict[str, MetricDeviation],
        baselines_map: Dict[str, CalibratedMetricBaseline],
        data_confidence_map: Dict[str, float]
    ) -> Tuple[List[AnomalyItem], List[HighlightItem], float]:
        """Detect confirmed anomalies, healthy highlights, and overall health score."""
        anomalies: List[AnomalyItem] = []
        highlights: List[HighlightItem] = []
        anom_counter = 1

        # Check anomalies per metric
        for metric_id, deviation in deviations_map.items():
            if metric_id not in baselines_map or metric_id not in features_map:
                continue

            baseline = baselines_map[metric_id]
            features = features_map[metric_id]
            data_conf = data_confidence_map.get(metric_id, 1.0)

            # Apply 4-layer noise filter
            filter_res = self.noise_filter.filter_metric(
                features=features,
                deviation=deviation,
                baseline=baseline,
                all_deviations=deviations_map
            )

            # Check if metric direction indicates problem vs healthy performance
            is_unfavorable = False
            if baseline.direction == OptimizationDirection.HIGHER_IS_BETTER:
                is_unfavorable = deviation.z_score < -0.5
            elif baseline.direction == OptimizationDirection.LOWER_IS_BETTER:
                is_unfavorable = deviation.z_score > 0.5
            else:
                is_unfavorable = abs(deviation.z_score) > 1.5

            if filter_res.passed and is_unfavorable:
                # Confirmed Anomaly
                corr_support = 1.0 if filter_res.correlated_metric_ids else 0.0
                sev_score = self.scorer.compute_score(
                    features=features,
                    deviation=deviation,
                    baseline=baseline,
                    correlation_support=corr_support,
                    data_confidence=data_conf,
                )
                sev_label = self.classifier.classify(sev_score)
                summary_text = AnomalySummaryGenerator.generate_summary(features, deviation, baseline)

                # Trend details (null out fields if < 6 points per spec)
                if features.has_trend_support:
                    trend_points = [
                        TrendPoint(period=item["period"], value=item["value"], z_score=item["z_score"])
                        for item in deviation.historical_z_scores
                    ]
                    trend_details = TrendDetails(
                        direction=features.trend_direction,
                        slope=features.slope,
                        acceleration=features.acceleration,
                        periods_deviating=deviation.periods_deviating,
                        values_over_time=trend_points,
                    )
                else:
                    trend_details = TrendDetails(
                        direction=features.trend_direction,
                        slope=None,
                        acceleration=None,
                        periods_deviating=None,
                        values_over_time=None,
                    )

                dev_details = DeviationDetails(
                    observed_current=deviation.observed_value,
                    expected_value=deviation.expected_mean,
                    expected_std=deviation.expected_std,
                    z_score=deviation.z_score,
                    percentile=deviation.percentile,
                    direction=deviation.direction,
                )

                anom_id = f"anom_{anom_counter:03d}"
                anom_counter += 1

                anomalies.append(
                    AnomalyItem(
                        anomaly_id=anom_id,
                        metric_id=metric_id,
                        metric_display_name=baseline.display_name,
                        category=baseline.category,
                        severity_score=sev_score,
                        severity_label=sev_label,
                        deviation=dev_details,
                        trend=trend_details,
                        correlated_anomalies=[],  # Linked in post-pass
                        noise_confidence=filter_res.noise_confidence,
                        context_tags=baseline.context_tags,
                        natural_language_summary=summary_text,
                    )
                )
            elif not is_unfavorable or abs(deviation.z_score) <= 1.0:
                # Healthy Metric Highlight
                note = f"{baseline.display_name} is performing at or above sector baseline ({deviation.percentile:.1f}th percentile)."
                highlights.append(
                    HighlightItem(
                        metric_id=metric_id,
                        status="healthy",
                        percentile=deviation.percentile,
                        note=note,
                    )
                )

        # Post-pass: link correlated anomaly IDs
        metric_to_anom_id = {a.metric_id: a.anomaly_id for a in anomalies}
        for anom in anomalies:
            corr_metrics = self.noise_filter.correlation_engine.get_correlated_metrics(
                anom.metric_id, threshold=self.thresholds.correlation_threshold
            )
            linked_ids = [metric_to_anom_id[m] for m in corr_metrics if m in metric_to_anom_id]
            anom.correlated_anomalies = linked_ids

        # Sort anomalies by severity descending
        anomalies.sort(key=lambda x: x.severity_score, reverse=True)

        # Compute overall company health score (0-100)
        overall_health = self._compute_overall_health(deviations_map, baselines_map)

        return anomalies, highlights, overall_health

    def _compute_overall_health(
        self,
        deviations_map: Dict[str, MetricDeviation],
        baselines_map: Dict[str, CalibratedMetricBaseline]
    ) -> float:
        """Compute weighted overall health score (0-100) from metric deviations."""
        if not deviations_map:
            return 50.0

        scores = []
        weights = []

        for metric_id, dev in deviations_map.items():
            if metric_id not in baselines_map:
                continue
            baseline = baselines_map[metric_id]
            weight = baseline.weight

            # Convert percentile into health contribution
            if baseline.direction == OptimizationDirection.HIGHER_IS_BETTER:
                metric_health = dev.percentile
            elif baseline.direction == OptimizationDirection.LOWER_IS_BETTER:
                metric_health = 100.0 - dev.percentile
            else:
                # Target band: optimal at 50th percentile
                dist_from_50 = abs(dev.percentile - 50.0)
                metric_health = max(0.0, 100.0 - (dist_from_50 * 2.0))

            scores.append(metric_health)
            weights.append(weight)

        if not scores:
            return 50.0

        total_weight = sum(weights)
        if total_weight <= 0:
            return float(np.mean(scores))

        weighted_health = sum(s * w for s, w in zip(scores, weights)) / total_weight
        return round(float(np.clip(weighted_health, 0.0, 100.0)), 1)
