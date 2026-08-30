from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from .config.loader import load_sector_config, load_thresholds
from .models.input_schema import CompanyInput, RevenueBand, SectorId
from .models.internal import MetricDeviation, MetricFeatures
from .models.output_schema import (
    AnomalyReport,
    CompanyProfileSummary,
    HighlightItem,
    ReportMetadata,
)
from .synthetic.correlations import CorrelationEngine
from .synthetic.generator import CalibratedMetricBaseline, SyntheticProfileGenerator
from .features.extractor import FeatureExtractor
from .features.normalizer import FeatureNormalizer
from .features.ratios import RatioCalculator
from .anomaly.detector import AnomalyDetector
from .anomaly.refusal import RefusalEvaluator


def analyze_company(
    input_data: CompanyInput,
    feedback_log_path: Optional[Any] = None,
) -> AnomalyReport:
    """Analyze company metrics against sector synthetic baseline and return AnomalyReport.

    This function is CPU-bound, deterministic, and requires no network I/O.
    """
    start_time = time.perf_counter()
    timestamp_str = datetime.now(timezone.utc).isoformat()

    # Load thresholds and sector config
    thresholds = load_thresholds()
    sector_cfg = load_sector_config(input_data.sector_id.value)
    profile_gen = SyntheticProfileGenerator(sector_cfg)
    metric_inputs_map = {m.metric_id: m for m in input_data.metrics}
    baselines_map = profile_gen.get_calibrated_profile(
        input_data.company_metadata.revenue_band,
        metric_inputs_map=metric_inputs_map,
    )

    # 1. Check for refusal conditions (e.g. all metrics < required periods or low confidence)
    refusal_details = RefusalEvaluator.evaluate_refusal(
        input_data, min_periods_required=thresholds.min_periods_for_trend
    )

    profile_summary = CompanyProfileSummary(
        revenue_band=input_data.company_metadata.revenue_band,
        employee_count=input_data.company_metadata.employee_count,
        region=input_data.company_metadata.region or "NA",
    )

    if refusal_details is not None:
        elapsed_ms = max(int((time.perf_counter() - start_time) * 1000), 1)
        metadata = ReportMetadata(
            model_version="0.1.0-mvp",
            synthetic_profile_version=sector_cfg.version,
            noise_filter_config={
                "z_threshold_flag": thresholds.z_threshold_flag,
                "z_threshold_alert": thresholds.z_threshold_alert,
                "min_persistence_periods": thresholds.min_persistence_periods,
                "correlation_threshold": thresholds.correlation_threshold,
            },
            metrics_analyzed=len(input_data.metrics),
            metrics_with_anomalies=0,
            metrics_with_missing_data=0,
            skipped_metrics=[],
            processing_time_ms=elapsed_ms,
        )

        return AnomalyReport(
            company_id=input_data.company_id,
            sector_id=input_data.sector_id,
            analysis_timestamp=timestamp_str,
            reporting_period=input_data.reporting_period,
            company_profile_summary=profile_summary,
            overall_health_score=None,
            anomalies=[],
            non_anomalous_highlights=[],
            refusal=refusal_details,
            metadata=metadata,
        )

    # 2. Extract features for each metric
    extractor = FeatureExtractor(min_periods_for_trend=thresholds.min_periods_for_trend)
    normalizer = FeatureNormalizer(z_threshold_flag=thresholds.z_threshold_flag)

    features_map: Dict[str, MetricFeatures] = {}
    deviations_map: Dict[str, MetricDeviation] = {}
    data_confidence_map: Dict[str, float] = {}
    missing_data_count = 0
    skipped_metrics: List[str] = []

    for metric_in in input_data.metrics:
        m_id = metric_in.metric_id
        data_confidence_map[m_id] = metric_in.confidence

        if m_id not in baselines_map:
            missing_data_count += 1
            skipped_metrics.append(m_id)
            continue

        baseline = baselines_map[m_id]
        features = extractor.extract_features(metric_in, baseline.metric_def)
        features_map[m_id] = features

        deviation = normalizer.normalize(features, baseline)
        deviations_map[m_id] = deviation

        if features.interpolated_ratio > 0:
            missing_data_count += 1

    # 3. Detect Anomalies & Score
    corr_engine = CorrelationEngine(sector_cfg)
    sector_id_str = input_data.sector_id.value if hasattr(input_data.sector_id, "value") else str(input_data.sector_id)
    detector = AnomalyDetector(
        thresholds=thresholds,
        correlation_engine=corr_engine,
        sector_id=sector_id_str,
        feedback_log_path=feedback_log_path or Path("feedback.jsonl"),
        metric_ids=list(baselines_map.keys()),
    )
    metric_inputs_map = {m.metric_id: m for m in input_data.metrics}
    anomalies, highlights, health_score, filtered_metrics = detector.detect_anomalies(
        features_map=features_map,
        deviations_map=deviations_map,
        baselines_map=baselines_map,
        data_confidence_map=data_confidence_map,
        revenue_band=input_data.company_metadata.revenue_band,
        sector_config=sector_cfg,
        metric_inputs_map=metric_inputs_map,
    )

    # 3b. Evaluate contradictory evidence refusal
    contradictory_refusal = RefusalEvaluator.evaluate_contradictory_evidence(
        anomalies=anomalies,
        deviations_map=deviations_map,
        correlation_engine=corr_engine,
        threshold=thresholds.correlation_threshold,
    )
    if contradictory_refusal is not None:
        elapsed_ms = max(int((time.perf_counter() - start_time) * 1000), 1)
        metadata = ReportMetadata(
            model_version="0.1.0-mvp",
            synthetic_profile_version=sector_cfg.version,
            noise_filter_config={
                "z_threshold_flag": thresholds.z_threshold_flag,
                "z_threshold_alert": thresholds.z_threshold_alert,
                "min_persistence_periods": thresholds.min_persistence_periods,
                "correlation_threshold": thresholds.correlation_threshold,
            },
            metrics_analyzed=len(features_map),
            metrics_with_anomalies=len(anomalies),
            metrics_with_missing_data=missing_data_count,
            skipped_metrics=skipped_metrics,
            filtered_metrics=filtered_metrics,
            processing_time_ms=elapsed_ms,
        )
        return AnomalyReport(
            company_id=input_data.company_id,
            sector_id=input_data.sector_id,
            analysis_timestamp=timestamp_str,
            reporting_period=input_data.reporting_period,
            company_profile_summary=profile_summary,
            overall_health_score=None,
            anomalies=anomalies,
            non_anomalous_highlights=highlights,
            refusal=contradictory_refusal,
            metadata=metadata,
        )

    # 4. Derived cross-metric ratio highlights
    if "lifetime_value" in features_map and "customer_acquisition_cost" in features_map:
        ltv_val = features_map["lifetime_value"].latest_value
        cac_val = features_map["customer_acquisition_cost"].latest_value
        ltv_cac = RatioCalculator.compute_ltv_cac(ltv_val, cac_val)
        if ltv_cac is not None:
            if ltv_cac >= 3.0:
                note = f"LTV/CAC ratio is {ltv_cac:.2f}x (healthy — industry target is ≥3.0x)"
                status = "healthy"
            elif ltv_cac >= 1.0:
                note = f"LTV/CAC ratio is {ltv_cac:.2f}x (borderline — below the 3.0x industry benchmark)"
                status = "warning"
            else:
                note = f"LTV/CAC ratio is {ltv_cac:.2f}x (critical — acquisition cost exceeds customer value)"
                status = "critical"
            highlights.append(
                HighlightItem(
                    metric_id="ltv_cac_ratio",
                    status=status,
                    percentile=min(float(ltv_cac / 5.0 * 100), 99.0),
                    note=note,
                )
            )

    if input_data.company_metadata.annual_revenue is not None and input_data.company_metadata.employee_count > 0:
        rev_per_emp = RatioCalculator.compute_revenue_per_employee(
            input_data.company_metadata.annual_revenue,
            input_data.company_metadata.employee_count
        )
        if rev_per_emp is not None:
            highlights.append(
                HighlightItem(
                    metric_id="revenue_per_employee",
                    status="healthy",
                    percentile=50.0,
                    note=f"Annual revenue per employee is ${rev_per_emp:,.0f}",
                )
            )

    elapsed_ms = max(int((time.perf_counter() - start_time) * 1000), 1)

    metadata = ReportMetadata(
        model_version="0.1.0-mvp",
        synthetic_profile_version=sector_cfg.version,
        noise_filter_config={
            "z_threshold_flag": thresholds.z_threshold_flag,
            "z_threshold_alert": thresholds.z_threshold_alert,
            "min_persistence_periods": thresholds.min_persistence_periods,
            "correlation_threshold": thresholds.correlation_threshold,
        },
        metrics_analyzed=len(features_map),
        metrics_with_anomalies=len(anomalies),
        metrics_with_missing_data=missing_data_count,
        skipped_metrics=skipped_metrics,
        filtered_metrics=filtered_metrics,
        processing_time_ms=elapsed_ms,
    )

    return AnomalyReport(
        company_id=input_data.company_id,
        sector_id=input_data.sector_id,
        analysis_timestamp=timestamp_str,
        reporting_period=input_data.reporting_period,
        company_profile_summary=profile_summary,
        overall_health_score=health_score,
        anomalies=anomalies,
        non_anomalous_highlights=highlights,
        refusal=None,
        metadata=metadata,
    )
