"""Time-series personalised baseline using Holt-Winters ETS.

Replaces the static parametric baseline when the user has >= 6 periods of history.
Falls back to the sector YAML baseline for < 6 periods.
"""

from typing import List, Tuple
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def fit_ets_baseline(
    values: List[float],
    horizon: int = 1,
    damped_trend: bool = True,
) -> Tuple[float, float]:
    """Fit Holt-Winters ETS on the observed series.

    Args:
        values: Chronological list of observed metric values (oldest first).
        horizon: Forecast horizon in periods (default 1 = next period).
        damped_trend: Whether to damp the trend component (reduces over-extrapolation).

    Returns:
        (forecast_mean, forecast_std) for the next `horizon` periods.

    Raises:
        ValueError: If len(values) < 6 (insufficient history).
    """
    if len(values) < 6:
        raise ValueError(
            f"ETS baseline requires >= 6 periods; got {len(values)}. "
            "Falling back to sector-parametric baseline."
        )

    model = ExponentialSmoothing(
        values,
        trend="add",
        damped_trend=damped_trend,
        initialization_method="estimated",
    )
    fit = model.fit(optimized=True)
    forecast = fit.forecast(horizon)
    residual_std = float(np.std(fit.resid))

    return float(forecast[-1]), max(residual_std, 1e-6)
