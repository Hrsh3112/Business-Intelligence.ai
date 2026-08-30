"""Pydantic schemas for ml_engine configurations."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class DistributionType(str, Enum):
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    UNIFORM = "uniform"


class MetricUnit(str, Enum):
    PERCENTAGE = "percentage"
    CURRENCY_USD = "currency_usd"
    RATIO = "ratio"
    COUNT = "count"


class OptimizationDirection(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    TARGET_BAND = "target_band"


class DistributionParams(BaseModel):
    mean: float
    std: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class DistributionConfig(BaseModel):
    type: DistributionType = DistributionType.NORMAL
    params: DistributionParams


class SeasonalityConfig(BaseModel):
    enabled: bool = False
    period: str = "quarterly"
    amplitude: float = 0.0


class RevenueBandAdjustment(BaseModel):
    band: str
    mean_adjustment: float = 0.0
    std_adjustment: float = 0.0


class SizeScalingConfig(BaseModel):
    revenue_bands: List[RevenueBandAdjustment] = Field(default_factory=list)


class MetricDefinition(BaseModel):
    metric_id: str
    display_name: str
    category: str
    unit: MetricUnit
    valid_min: float
    valid_max: float
    direction: OptimizationDirection = OptimizationDirection.HIGHER_IS_BETTER
    distribution: DistributionConfig
    seasonality: SeasonalityConfig = Field(default_factory=SeasonalityConfig)
    size_scaling: SizeScalingConfig = Field(default_factory=SizeScalingConfig)
    correlation_group: Optional[str] = None
    weight: float = Field(default=1.0, ge=0.0, le=2.0)
    context_tags: List[str] = Field(default_factory=list)


class SectorConfig(BaseModel):
    sector_id: str
    sector_name: str
    version: str = "2026-07-01"
    metrics: List[MetricDefinition]
    correlation_matrix: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    revenue_band_impact_weights: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class ThresholdsConfig(BaseModel):
    z_threshold_flag: float = 1.5
    z_threshold_alert: float = 2.5
    min_persistence_periods: int = 2
    correlation_threshold: float = 0.5
    urgency_acceleration_threshold: float = 0.1
    enable_ets_baseline: bool = False
    min_periods_for_trend: Union[Dict[str, int], int] = Field(
        default_factory=lambda: {"monthly": 6, "quarterly": 4, "annual": 3}
    )
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "magnitude": 30.0,
            "persistence": 20.0,
            "trajectory": 20.0,
            "importance": 15.0,
            "support": 15.0,
        }
    )
    classification_cutoffs: Dict[str, float] = Field(
        default_factory=lambda: {
            "warning": 25.0,
            "critical": 50.0,
            "severe": 75.0,
        }
    )

    def get_min_periods(self, granularity: str) -> int:
        """Get required minimum periods for full trend analysis for a given granularity."""
        if isinstance(self.min_periods_for_trend, dict):
            return self.min_periods_for_trend.get(granularity.lower(), 6)
        return int(self.min_periods_for_trend)
