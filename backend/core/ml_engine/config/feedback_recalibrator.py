"""Bayesian threshold recalibration from analyst feedback.

Uses Beta-Binomial conjugate update to estimate the 'noise rate' for each
(sector, metric_id) pair and adjusts the L1 z-score threshold accordingly.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import time

BASE_THRESHOLD = 1.5  # default L1 z-score threshold
MAX_ADJUSTMENT = 0.8  # cap: threshold never exceeds BASE + MAX_ADJUSTMENT (2.3)
MIN_FEEDBACK_COUNT = 5  # cold-start guard: require >= 5 feedback points before adjusting

_CACHE: Dict[str, tuple[float, Dict[str, float]]] = {}
_CACHE_TTL = 60.0  # seconds


def compute_adjusted_threshold(
    sector: str,
    metric_id: str,
    feedback_log: Optional[Path] = None,
    base: float = BASE_THRESHOLD,
) -> float:
    """Beta-Binomial Bayesian update on z-score threshold.

    Prior: Beta(1, 1) — uniform, no prior preference.
    Likelihood: each 'not_useful' feedback = noise signal (increments negatives).
                each 'useful' feedback = true positive signal (increments positives).

    Posterior mean noise rate = negatives / (positives + negatives).
    Adjusted threshold = base + noise_rate * MAX_ADJUSTMENT.

    Args:
        sector: e.g. "tech_saas"
        metric_id: e.g. "churn_rate"
        feedback_log: Path to feedback.jsonl
        base: Base threshold (default 1.5)

    Returns:
        Adjusted threshold, rounded to 2dp.
    """
    if feedback_log is None or not Path(feedback_log).exists():
        return base

    positives = 1  # Beta prior alpha
    negatives = 1  # Beta prior beta
    feedback_count = 0

    try:
        lines = Path(feedback_log).read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                fb = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue

            fb_sector = fb.get("sector") or fb.get("sector_id")
            fb_metric = fb.get("metric_id")
            # If target was anomaly, check matching sector and metric_id
            if fb_sector != sector or fb_metric != metric_id:
                continue

            rating = fb.get("rating") or fb.get("verdict")
            if rating == "useful":
                positives += 1
                feedback_count += 1
            elif rating == "not_useful":
                negatives += 1
                feedback_count += 1

        # Cold-start guard: if fewer than MIN_FEEDBACK_COUNT entries, stay at base
        if feedback_count < MIN_FEEDBACK_COUNT:
            return base

        noise_rate = negatives / (positives + negatives)
        adjusted = base + noise_rate * MAX_ADJUSTMENT
        return round(float(min(adjusted, base + MAX_ADJUSTMENT)), 2)
    except Exception:
        return base


def build_threshold_map(
    sector: str,
    metric_ids: List[str],
    feedback_log: Optional[Path] = None,
) -> Dict[str, float]:
    """Build a full {metric_id: threshold} map for all metrics in a sector with caching."""
    if not metric_ids:
        return {}

    cache_key = f"{sector}:{str(feedback_log)}"
    now = time.time()
    if cache_key in _CACHE:
        cached_ts, cached_map = _CACHE[cache_key]
        if now - cached_ts < _CACHE_TTL:
            return {m: cached_map.get(m, BASE_THRESHOLD) for m in metric_ids}

    threshold_map = {
        m: compute_adjusted_threshold(sector, m, feedback_log)
        for m in metric_ids
    }
    _CACHE[cache_key] = (now, threshold_map)
    return threshold_map
