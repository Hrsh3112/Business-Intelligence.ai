"""Cost estimation for the one LLM call in the pipeline (Stage 1 — telemetry).

Kept out of pipeline.py deliberately: the orchestrator routes, times and
catches, it does not compute. This module owns the arithmetic and the honesty
rules around it, and pipeline.py makes exactly one call into it.

The honesty rules, since this number is shown to a user:

  * No entry in llm_pricing.yaml for the model  -> cost is None, and the
    reason says so. We never guess a rate.
  * No token count reported                     -> cost is None. We never
    substitute 0 for unknown.
  * A cost that IS produced always travels with the basis it was derived
    from, so "where did $0.0004 come from?" has an answer.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from api.models.internal import CostEstimate

_PRICING_PATH = Path(__file__).parent / "llm_pricing.yaml"


@lru_cache(maxsize=1)
def load_pricing() -> dict:
    with open(_PRICING_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def models() -> dict:
    return load_pricing().get("models", {})


def estimate_cost(llm_model: Optional[str], tokens_used: Optional[int]) -> CostEstimate:
    """Never raises, never invents. Returns a CostEstimate whose `estimated_usd`
    is None whenever we cannot stand behind a figure."""
    if not llm_model or tokens_used is None:
        return CostEstimate(
            llm_model=llm_model,
            tokens_used=tokens_used,
            estimated_usd=None,
            basis="no LLM call was made, or no token count was reported",
        )

    entry = models().get(llm_model)
    if entry is None or entry.get("blended_usd_per_1m") is None:
        return CostEstimate(
            llm_model=llm_model,
            tokens_used=tokens_used,
            estimated_usd=None,
            basis=f"no published rate configured for '{llm_model}'",
        )

    rate = float(entry["blended_usd_per_1m"])
    # Rounded to 6dp: these are sub-cent figures and floating-point tails read
    # as false precision in the UI.
    estimated = round(tokens_used / 1_000_000 * rate, 6)
    return CostEstimate(
        llm_model=llm_model,
        tokens_used=tokens_used,
        estimated_usd=estimated,
        basis=f"{tokens_used:,} tokens @ ${rate}/1M — {entry.get('basis', 'configured rate')}",
    )
