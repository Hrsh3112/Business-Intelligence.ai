"""Synthetic data generation and baseline estimation package."""

from .correlations import CorrelationEngine
from .distributions import compute_percentile, compute_z_score, sample_distribution
from .generator import CalibratedMetricBaseline, SyntheticProfileGenerator

__all__ = [
    "compute_z_score",
    "compute_percentile",
    "sample_distribution",
    "CorrelationEngine",
    "CalibratedMetricBaseline",
    "SyntheticProfileGenerator",
]
