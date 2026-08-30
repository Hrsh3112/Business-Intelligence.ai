"""L1b — Multivariate anomaly detection using Isolation Forest.

Operates on the cross-metric value matrix and flags periods that are
anomalous as a combination, even if individual metrics are below univariate thresholds.
"""

from typing import Dict, List
import numpy as np
from sklearn.ensemble import IsolationForest


def run_isolation_forest(
    metric_matrix: np.ndarray,
    contamination: float = 0.1,
    random_state: int = 42,
) -> np.ndarray:
    """Detect multivariate anomalies across periods.

    Args:
        metric_matrix: Array of shape (n_periods, n_metrics). NaN-filled columns are dropped.
        contamination: Expected proportion of anomalous periods.
        random_state: Seed for reproducibility.

    Returns:
        Boolean array of shape (n_periods,): True = multivariate anomaly detected.

    Notes:
        Requires n_periods >= 8 and n_metrics >= 2; returns all-False otherwise.
    """
    if metric_matrix is None or metric_matrix.size == 0:
        return np.array([], dtype=bool)

    if metric_matrix.ndim != 2:
        return np.zeros(metric_matrix.shape[0] if metric_matrix.ndim > 0 else 0, dtype=bool)

    n_periods, n_metrics = metric_matrix.shape
    if n_periods < 8 or n_metrics < 2:
        return np.zeros(n_periods, dtype=bool)

    # Drop columns with any NaN or infinite values
    valid_cols = ~np.any(np.isnan(metric_matrix) | np.isinf(metric_matrix), axis=0)
    if valid_cols.sum() < 2:
        return np.zeros(n_periods, dtype=bool)

    X = metric_matrix[:, valid_cols]
    clf = IsolationForest(
        contamination=contamination,
        random_state=random_state,
        n_jobs=1,
    )
    preds = clf.fit_predict(X)  # -1 = anomaly, 1 = inlier
    return preds == -1


def build_metric_matrix(metric_values_map: Dict[str, List[float]]) -> np.ndarray:
    """Build a 2D numpy array of shape (n_periods, n_metrics) from metric time series.

    Trims series to the shortest common length across metrics.
    """
    if not metric_values_map or len(metric_values_map) < 2:
        return np.empty((0, 0))

    valid_series = {k: v for k, v in metric_values_map.items() if v and len(v) > 0}
    if len(valid_series) < 2:
        return np.empty((0, 0))

    min_len = min(len(v) for v in valid_series.values())
    if min_len == 0:
        return np.empty((0, 0))

    # Slice each series to the most recent min_len periods
    cols = [np.array(v[-min_len:], dtype=float) for v in valid_series.values()]
    return np.column_stack(cols)
