"""Synthetic Profile Generator for businessintelligence.ai.

Generates calibrated 'ideal company' baseline distributions customized by sector and size cohort.
"""

from typing import Dict, List, Optional
import numpy as np
from ..config.schema import (
    DistributionConfig,
    DistributionParams,
    MetricDefinition,
    SectorConfig,
)
from ..models.input_schema import RevenueBand, SectorId
from .distributions import sample_distribution


class CalibratedMetricBaseline:
    """Calibrated baseline parameters for a metric given sector and size cohort."""

    def __init__(
        self,
        metric_def: MetricDefinition,
        calibrated_mean: float,
        calibrated_std: float,
        lower_bound: Optional[float] = None,
        upper_bound: Optional[float] = None
    ):
        self.metric_def = metric_def
        self.metric_id = metric_def.metric_id
        self.display_name = metric_def.display_name
        self.category = metric_def.category
        self.unit = metric_def.unit
        self.direction = metric_def.direction
        self.weight = metric_def.weight
        self.context_tags = metric_def.context_tags
        self.mean = calibrated_mean
        self.std = max(calibrated_std, 1e-4)
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound

    def sample(self, n_samples: int = 1, seed: Optional[int] = None) -> np.ndarray:
        """Sample synthetic ideal observations."""
        cfg = DistributionConfig(
            type=self.metric_def.distribution.type,
            params=DistributionParams(
                mean=self.mean,
                std=self.std,
                lower_bound=self.lower_bound,
                upper_bound=self.upper_bound,
            )
        )
        return sample_distribution(cfg, n_samples=n_samples, seed=seed)


class SyntheticProfileGenerator:
    """Generates customized ideal synthetic profiles by sector and revenue band."""

    def __init__(self, sector_config: SectorConfig):
        self.sector_config = sector_config
        self.metric_defs: Dict[str, MetricDefinition] = {
            m.metric_id: m for m in sector_config.metrics
        }

    def get_calibrated_profile(
        self,
        revenue_band: RevenueBand
    ) -> Dict[str, CalibratedMetricBaseline]:
        """Compute size-adjusted baseline expectations for each metric in the sector."""
        profile = {}
        for metric_id, metric_def in self.metric_defs.items():
            base_params = metric_def.distribution.params
            mean = base_params.mean
            std = base_params.std

            # Apply size scaling adjustment if present
            band_str = revenue_band.value if isinstance(revenue_band, RevenueBand) else str(revenue_band)
            for adj in metric_def.size_scaling.revenue_bands:
                if adj.band == band_str:
                    mean += adj.mean_adjustment
                    std = max(std + adj.std_adjustment, 0.01)
                    break

            profile[metric_id] = CalibratedMetricBaseline(
                metric_def=metric_def,
                calibrated_mean=mean,
                calibrated_std=std,
                lower_bound=base_params.lower_bound,
                upper_bound=base_params.upper_bound,
            )
        return profile

    def generate_synthetic_cohort(
        self,
        revenue_band: RevenueBand,
        n_companies: int = 100,
        seed: Optional[int] = 42
    ) -> Dict[str, np.ndarray]:
        """Generate a synthetic cohort of healthy companies for validation and testing."""
        profile = self.get_calibrated_profile(revenue_band)
        cohort = {}
        for metric_id, baseline in profile.items():
            cohort[metric_id] = baseline.sample(n_samples=n_companies, seed=seed)
        return cohort
