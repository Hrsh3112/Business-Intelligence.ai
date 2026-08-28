"""Statistical distribution utilities for synthetic baseline generation and evaluation."""

import numpy as np
from scipy import stats
from typing import Optional, Tuple
from ..config.schema import DistributionConfig, DistributionType


def compute_z_score(observed: float, mean: float, std: float) -> float:
    """Compute z-score: number of standard deviations from mean."""
    if std <= 1e-9:
        return 0.0 if np.isclose(observed, mean) else float("inf")
    return float((observed - mean) / std)


def compute_percentile(observed: float, mean: float, std: float) -> float:
    """Compute cumulative distribution function percentile (0.0 to 100.0)."""
    if std <= 1e-9:
        return 50.0 if np.isclose(observed, mean) else (100.0 if observed > mean else 0.0)
    z = (observed - mean) / std
    pct = stats.norm.cdf(z) * 100.0
    return float(np.clip(pct, 0.01, 99.99))


def sample_distribution(
    dist_config: DistributionConfig,
    n_samples: int = 1,
    seed: Optional[int] = None
) -> np.ndarray:
    """Sample values from configured distribution, applying bounds."""
    rng = np.random.default_rng(seed)
    params = dist_config.params

    if dist_config.type == DistributionType.NORMAL:
        samples = rng.normal(loc=params.mean, scale=max(params.std, 1e-6), size=n_samples)
    elif dist_config.type == DistributionType.LOGNORMAL:
        # If lognormal, params mean and std are interpreted in real space
        # Convert to log-space mu and sigma
        variance = params.std ** 2
        mu_log = np.log((params.mean ** 2) / np.sqrt(variance + params.mean ** 2))
        sigma_log = np.sqrt(np.log(1.0 + (variance / (params.mean ** 2))))
        samples = rng.lognormal(mean=mu_log, sigma=sigma_log, size=n_samples)
    elif dist_config.type == DistributionType.UNIFORM:
        low = params.lower_bound if params.lower_bound is not None else params.mean - params.std
        high = params.upper_bound if params.upper_bound is not None else params.mean + params.std
        samples = rng.uniform(low=low, high=high, size=n_samples)
    else:
        samples = rng.normal(loc=params.mean, scale=max(params.std, 1e-6), size=n_samples)

    # Clamp bounds if specified
    if params.lower_bound is not None:
        samples = np.maximum(samples, params.lower_bound)
    if params.upper_bound is not None:
        samples = np.minimum(samples, params.upper_bound)

    return samples
