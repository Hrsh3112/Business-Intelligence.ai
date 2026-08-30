"""Granger causality test for driver directionality within anomaly clusters.

Determines whether metric A temporally precedes and predicts metric B.
Requires >= 10 periods for reliable results.

Reference: statsmodels.tsa.stattools.grangercausalitytests
"""

import warnings
from typing import Dict, List, Set
import numpy as np
from statsmodels.tsa.stattools import grangercausalitytests

from ..models.output_schema import AnomalyItem

MIN_PERIODS_FOR_GRANGER = 10
DEFAULT_MAX_LAG = 2
DEFAULT_P_THRESHOLD = 0.05


def granger_causes(
    series_a: List[float],
    series_b: List[float],
    max_lag: int = DEFAULT_MAX_LAG,
    p_threshold: float = DEFAULT_P_THRESHOLD,
) -> bool:
    """Test whether series_a Granger-causes series_b.

    Returns True if lagged values of A significantly predict B
    (min p-value across lags < p_threshold).
    Returns False if insufficient data or test fails.
    """
    if len(series_a) < MIN_PERIODS_FOR_GRANGER or len(series_b) < MIN_PERIODS_FOR_GRANGER:
        return False

    min_len = min(len(series_a), len(series_b))
    a = np.array(series_a[-min_len:], dtype=float)
    b = np.array(series_b[-min_len:], dtype=float)

    # Check for constant series or zero variance
    if np.std(a) < 1e-8 or np.std(b) < 1e-8:
        return False

    # [caused, causing] per statsmodels convention: [series_b, series_a]
    data = np.column_stack([b, a])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = grangercausalitytests(data, maxlag=max_lag)
        p_values = [results[lag][0]["ssr_ftest"][1] for lag in range(1, max_lag + 1)]
        return float(min(p_values)) < p_threshold
    except Exception:
        return False


def rank_cluster_by_granger(
    cluster: List[AnomalyItem],
    series_map: Dict[str, List[float]],
    max_lag: int = DEFAULT_MAX_LAG,
) -> List[AnomalyItem]:
    """Within a cluster of anomalies, use Granger tests to promote the earliest causal driver.

    Returns the cluster with `driver_rank` updated: 1 = Granger-identified driver, 0 = symptom.
    Sets `granger_tested = True` on all anomalies in the cluster if Granger testing was applied.
    Falls back to existing magnitude ranking if Granger is inconclusive.
    """
    if len(cluster) < 2:
        return cluster

    ids = [a.metric_id for a in cluster]
    granger_adj: Dict[str, Set[str]] = {mid: set() for mid in ids}

    for i, a_id in enumerate(ids):
        for j, b_id in enumerate(ids):
            if i == j:
                continue
            if a_id in series_map and b_id in series_map:
                if granger_causes(series_map[a_id], series_map[b_id], max_lag=max_lag):
                    granger_adj[a_id].add(b_id)

    cause_counts = {mid: len(caused) for mid, caused in granger_adj.items()}
    max_causes = max(cause_counts.values()) if cause_counts else 0

    if max_causes == 0:
        # Inconclusive — retain existing rankings
        return cluster

    best_driver_id = max(cause_counts, key=lambda x: cause_counts[x])

    for a in cluster:
        a.driver_rank = 1 if a.metric_id == best_driver_id else 0
        a.granger_tested = True

    return cluster
