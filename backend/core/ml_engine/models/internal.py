"""Internal data structures for feature extraction, comparison, and filtering."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .output_schema import DeviationDirection, TrendDirection


@dataclass
class MetricFeatures:
    """Extracted statistical and time-series features for a metric."""
    metric_id: str
    latest_value: float
    mean: float
    std: float
    slope: Optional[float] = None
    acceleration: Optional[float] = None
    volatility: float = 0.0
    num_points: int = 0
    interpolated_ratio: float = 0.0
    has_trend_support: bool = False
    trend_direction: TrendDirection = TrendDirection.STABLE
    values_with_periods: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class MetricDeviation:
    """Deviation metrics against synthetic ideal baseline."""
    metric_id: str
    observed_value: float
    expected_mean: float
    expected_std: float
    z_score: float
    percentile: float
    direction: DeviationDirection
    severity_raw: float
    historical_z_scores: List[Dict[str, float]] = field(default_factory=list)
    periods_deviating: int = 0


@dataclass
class FilterResult:
    """Outcome of 4-layer noise filtering."""
    passed: bool
    l1_passed: bool
    l2_passed: bool
    l3_passed: bool
    l4_passed: bool
    noise_confidence: float
    rejection_reason: Optional[str] = None
    layer_failed: Optional[str] = None
    correlated_metric_ids: List[str] = field(default_factory=list)
