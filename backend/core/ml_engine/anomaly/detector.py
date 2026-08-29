"""Core anomaly detection and health assessment orchestrator."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from ..config.schema import OptimizationDirection, SectorConfig, ThresholdsConfig
from ..models.input_schema import RevenueBand
from ..models.internal import MetricDeviation, MetricFeatures
from ..models.output_schema import (
    AnomalyItem,
    DeviationDetails,
    HighlightItem,
    TrendDetails,
    TrendDirection,
    TrendPoint,
    UrgencyLabel,
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
        data_confidence_map: Dict[str, float],
        revenue_band: Optional[RevenueBand] = None,
        sector_config: Optional[SectorConfig] = None,
    ) -> Tuple[List[AnomalyItem], List[HighlightItem], float, List[Dict[str, Any]]]:
        """Detect confirmed anomalies, healthy highlights, overall health score, and filtered metrics."""
        anomalies: List[AnomalyItem] = []
        highlights: List[HighlightItem] = []
        filtered_metrics: List[Dict[str, Any]] = []
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
                urgency = self._compute_urgency(features, deviation)

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
                        driver_rank=0,            # Ranked in post-pass
                        candidate_explanations=[],# Populated in post-pass
                        decision_urgency=urgency,
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
            else:
                # Metric showed unfavorable deviation but was filtered out by noise sieve
                filtered_metrics.append({
                    "metric_id": metric_id,
                    "display_name": baseline.display_name,
                    "reason": filter_res.rejection_reason or "Filtered out by noise filter",
                    "layer": filter_res.layer_failed or "L1",
                })

        # Post-pass 1: link correlated anomaly IDs
        metric_to_anom_id = {a.metric_id: a.anomaly_id for a in anomalies}
        for anom in anomalies:
            corr_metrics = self.noise_filter.correlation_engine.get_correlated_metrics(
                anom.metric_id, threshold=self.thresholds.correlation_threshold
            )
            linked_ids = [metric_to_anom_id[m] for m in corr_metrics if m in metric_to_anom_id]
            anom.correlated_anomalies = linked_ids

        # Post-pass 2: rank drivers in correlated clusters
        self._rank_drivers(anomalies, baselines_map)

        # Post-pass 3: generate candidate explanations for weak-signal anomalies (< 0.5)
        for anom in anomalies:
            if anom.metric_id in baselines_map:
                anom.candidate_explanations = self._generate_candidate_explanations(
                    anom, baselines_map[anom.metric_id], deviations_map
                )

        # Sort anomalies by severity descending
        anomalies.sort(key=lambda x: x.severity_score, reverse=True)

        # Compute overall company health score (0-100)
        overall_health = self._compute_overall_health(
            deviations_map, baselines_map, revenue_band=revenue_band, sector_config=sector_config
        )

        return anomalies, highlights, overall_health, filtered_metrics

    def _compute_urgency(
        self,
        features: MetricFeatures,
        deviation: MetricDeviation
    ) -> UrgencyLabel:
        """Compute decision-urgency label from temporal slope and acceleration."""
        if features.trend_direction == TrendDirection.IMPROVING:
            return UrgencyLabel.IMPROVING
        if (
            features.has_trend_support
            and features.acceleration is not None
            and abs(features.acceleration) >= self.thresholds.urgency_acceleration_threshold
            and features.trend_direction == TrendDirection.DETERIORATING
        ):
            return UrgencyLabel.ESCALATING
        return UrgencyLabel.STABLE_BAD

    def _rank_drivers(
        self,
        anomalies: List[AnomalyItem],
        baselines_map: Dict[str, CalibratedMetricBaseline]
    ) -> None:
        """Assign driver_rank (1=primary driver, 0=symptom/standalone) using cluster lead-lag heuristics."""
        if not anomalies:
            return

        anom_map = {a.anomaly_id: a for a in anomalies}
        visited = set()

        for anom in anomalies:
            if anom.anomaly_id in visited:
                continue

            cluster: List[AnomalyItem] = []
            queue = [anom.anomaly_id]
            visited.add(anom.anomaly_id)

            while queue:
                curr_id = queue.pop(0)
                curr_anom = anom_map.get(curr_id)
                if curr_anom:
                    cluster.append(curr_anom)
                    for neighbor_id in curr_anom.correlated_anomalies:
                        if neighbor_id not in visited and neighbor_id in anom_map:
                            visited.add(neighbor_id)
                            queue.append(neighbor_id)

            if len(cluster) > 1:
                def driver_score(a: AnomalyItem) -> float:
                    z_mag = abs(a.deviation.z_score)
                    is_deteriorating = 1.0 if a.trend.direction == TrendDirection.DETERIORATING else 0.0
                    weight = baselines_map[a.metric_id].weight if a.metric_id in baselines_map else 1.0
                    return z_mag + (0.5 * is_deteriorating) + (0.2 * weight)

                best_driver = max(cluster, key=driver_score)
                for a in cluster:
                    a.driver_rank = 1 if a.anomaly_id == best_driver.anomaly_id else 0
            else:
                anom.driver_rank = 0

    def _generate_candidate_explanations(
        self,
        anom: AnomalyItem,
        baseline: CalibratedMetricBaseline,
        all_deviations: Dict[str, MetricDeviation],
    ) -> List[str]:
        """Generate competing deterministic explanations when noise_confidence < 0.5."""
        if anom.noise_confidence >= 0.5:
            return []

        explanations: List[str] = []
        # Hypothesis 1: Seasonal / Cyclical variation
        if baseline.metric_def.seasonality.enabled:
            explanations.append(
                f"Seasonal variance: movement may be influenced by {baseline.metric_def.seasonality.period} seasonal cycle (amplitude ±{baseline.metric_def.seasonality.amplitude})."
            )
        else:
            explanations.append(
                "Transient variation: movement may be temporary variance rather than persistent structural change."
            )

        # Hypothesis 2: Correlated symptom / co-movement
        corr_metrics = self.noise_filter.correlation_engine.get_correlated_metrics(
            anom.metric_id, threshold=self.thresholds.correlation_threshold
        )
        linked_corr = [m for m in corr_metrics if m in all_deviations]
        if linked_corr:
            explanations.append(
                f"Co-movement symptom: correlated deviation observed alongside {', '.join(linked_corr[:2])}."
            )
        else:
            explanations.append(
                "Isolated divergence: metric is deviating independently without confirming signals from related KPIs."
            )

        return explanations

    def _compute_overall_health(
        self,
        deviations_map: Dict[str, MetricDeviation],
        baselines_map: Dict[str, CalibratedMetricBaseline],
        revenue_band: Optional[RevenueBand] = None,
        sector_config: Optional[SectorConfig] = None,
    ) -> float:
        """Compute weighted overall health score (0-100) from metric deviations and revenue band impact multipliers."""
        if not deviations_map:
            return 50.0

        scores = []
        weights = []

        band_multipliers: Dict[str, float] = {}
        if sector_config and revenue_band:
            band_key = revenue_band.value if hasattr(revenue_band, "value") else str(revenue_band)
            band_multipliers = sector_config.revenue_band_impact_weights.get(band_key, {})

        for metric_id, dev in deviations_map.items():
            if metric_id not in baselines_map:
                continue
            baseline = baselines_map[metric_id]
            base_weight = baseline.weight

            mult = band_multipliers.get(metric_id, 1.0)
            weight = min(base_weight * mult, 3.0 * base_weight)

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
