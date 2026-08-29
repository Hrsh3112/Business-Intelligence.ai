from typing import Any, Dict, List, Optional, Union
from ..models.input_schema import CompanyInput
from ..models.internal import MetricDeviation
from ..models.output_schema import AnomalyItem, RefusalDetails, RefusalReason


class RefusalEvaluator:
    """Evaluates whether an input payload fails criteria and requires a structured refusal."""

    @staticmethod
    def evaluate_refusal(
        company_input: CompanyInput,
        min_periods_required: Union[Dict[str, int], int] = 6
    ) -> Optional[RefusalDetails]:
        """Check if analysis must be refused."""
        if not company_input.metrics:
            return RefusalDetails(
                reason=RefusalReason.INSUFFICIENT_DATA,
                message="No metrics were provided in the input payload.",
                diagnostic_suggestion="Please include at least one time series metric.",
                missing_metrics=[]
            )

        # Check if ALL metrics have extremely low confidence (< 0.35)
        confidences = [m.confidence for m in company_input.metrics]
        if confidences and all(c < 0.35 for c in confidences):
            return RefusalDetails(
                reason=RefusalReason.LOW_CONFIDENCE,
                message="All submitted metrics have low data confidence (< 0.35), preventing reliable anomaly detection.",
                diagnostic_suggestion="Please review data ingestion sources or provide direct user-entered metrics with confidence >= 0.5.",
                missing_metrics=[],
            )

        # Check if ALL metrics have fewer than minimum required periods for their granularity
        all_short = True
        metric_ids = []
        for m in company_input.metrics:
            metric_ids.append(m.metric_id)
            if isinstance(min_periods_required, dict):
                gran = m.granularity.value.lower() if hasattr(m.granularity, "value") else str(m.granularity).lower()
                min_req = min_periods_required.get(gran, 6)
            else:
                min_req = int(min_periods_required)

            if len(m.values) >= min_req:
                all_short = False
                break

        if all_short:
            return RefusalDetails(
                reason=RefusalReason.INSUFFICIENT_DATA,
                message=(
                    "All submitted metrics have fewer than the required periods (6 monthly / 4 quarterly / 3 annual) "
                    "for structural anomaly and trend analysis (newly launched or sparse-history KPI)."
                ),
                diagnostic_suggestion=(
                    "Please provide at least 6 monthly, 4 quarterly, or 3 annual periods of historical data "
                    "for one or more metrics to enable statistical persistence and trend evaluation."
                ),
                missing_metrics=metric_ids,
            )

        return None

    @staticmethod
    def evaluate_contradictory_evidence(
        anomalies: List[AnomalyItem],
        deviations_map: Dict[str, MetricDeviation],
        correlation_engine: Any,
        threshold: float = 0.5,
    ) -> Optional[RefusalDetails]:
        """
        Returns a CONTRADICTORY_EVIDENCE refusal if strong conflicting signals exist.

        Condition: an anomaly (|z| >= 2.0) has a highly correlated peer (|coeff| >= threshold)
        deviating strongly in the opposite direction from what the correlation predicts.
        """
        conflicting_pairs = []
        for anom in anomalies:
            corr_metrics = correlation_engine.get_correlated_metrics(
                anom.metric_id, threshold=threshold
            )
            for other_id in corr_metrics:
                if other_id in deviations_map:
                    other_dev = deviations_map[other_id]
                    corr = correlation_engine.get_correlation(anom.metric_id, other_id)
                    co_dev_sign = anom.deviation.z_score * other_dev.z_score * corr
                    if co_dev_sign < -0.8 and abs(anom.deviation.z_score) >= 2.0 and abs(other_dev.z_score) >= 2.0:
                        conflicting_pairs.append((anom.metric_id, other_id))

        if conflicting_pairs:
            metric_ids = sorted(list(set([p[0] for p in conflicting_pairs] + [p[1] for p in conflicting_pairs])))
            pair_strs = [f"{p[0]} vs {p[1]}" for p in conflicting_pairs[:2]]
            return RefusalDetails(
                reason=RefusalReason.CONTRADICTORY_EVIDENCE,
                message=(
                    f"Strong contradictory signals detected between correlated metrics ({', '.join(pair_strs)}). "
                    "The observed opposing movements violate domain relationships, preventing reliable diagnostic attribution."
                ),
                diagnostic_suggestion=(
                    "Verify data accuracy, definitions, or reporting periods for the conflicting metrics to ensure consistent data inputs."
                ),
                missing_metrics=metric_ids,
            )

        return None

