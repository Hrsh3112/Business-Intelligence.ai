"""Tests for synthetic distribution generation and sector configs."""

import pytest
import numpy as np
from ml_engine.config.loader import (
    get_all_canonical_metrics,
    get_metric_definition,
    list_supported_sectors,
    load_sector_config,
)
from ml_engine.models.input_schema import RevenueBand
from ml_engine.synthetic.distributions import (
    compute_percentile,
    compute_z_score,
)
from ml_engine.synthetic.generator import SyntheticProfileGenerator


def test_supported_sectors():
    """Verify supported sectors list."""
    sectors = list_supported_sectors()
    assert "TECH_SAAS" in sectors
    assert "RETAIL" in sectors


def test_sector_config_loading():
    """Verify sector config loads properly."""
    saas_cfg = load_sector_config("TECH_SAAS")
    assert saas_cfg.sector_id == "TECH_SAAS"
    assert len(saas_cfg.metrics) >= 7

    retail_cfg = load_sector_config("RETAIL")
    assert retail_cfg.sector_id == "RETAIL"
    assert len(retail_cfg.metrics) >= 8
    retail_metric_ids = [m.metric_id for m in retail_cfg.metrics]
    assert "same_store_sales_growth" in retail_metric_ids
    assert "sell_through_rate" in retail_metric_ids
    assert "customer_acquisition_cost" in retail_metric_ids
    assert "return_rate" in retail_metric_ids


def test_metric_catalog():
    """Verify canonical metric catalog export."""
    catalog = get_all_canonical_metrics()
    assert "TECH_SAAS" in catalog
    assert "RETAIL" in catalog
    assert "monthly_recurring_revenue_growth" in catalog["TECH_SAAS"]
    assert catalog["TECH_SAAS"]["monthly_recurring_revenue_growth"]["unit"] == "percentage"
    assert "same_store_sales_growth" in catalog["RETAIL"]
    assert catalog["RETAIL"]["same_store_sales_growth"]["unit"] == "percentage"


def test_size_scaling_calibration():
    """Verify size scaling adjustments alter mean and std appropriately."""
    saas_cfg = load_sector_config("TECH_SAAS")
    generator = SyntheticProfileGenerator(saas_cfg)

    # <1M vs >100M for MRR growth
    profile_small = generator.get_calibrated_profile(RevenueBand.UNDER_1M)
    profile_large = generator.get_calibrated_profile(RevenueBand.OVER_100M)

    # Early stage startups have higher expected growth than mega corps
    assert profile_small["monthly_recurring_revenue_growth"].mean > profile_large["monthly_recurring_revenue_growth"].mean


def test_distribution_sampling():
    """Verify synthetic sampling stays within bounds and generates valid stats."""
    saas_cfg = load_sector_config("TECH_SAAS")
    generator = SyntheticProfileGenerator(saas_cfg)
    cohort = generator.generate_synthetic_cohort(RevenueBand.ONE_TO_10M, n_companies=500, seed=42)

    mrr_samples = cohort["monthly_recurring_revenue_growth"]
    assert len(mrr_samples) == 500
    assert np.mean(mrr_samples) > 5.0  # reasonable mean
    assert np.all(mrr_samples >= -10.0)  # respects lower bound


def test_z_score_and_percentile():
    """Verify mathematical correctness of z-score and percentile calculations."""
    z = compute_z_score(observed=10.0, mean=10.0, std=2.0)
    assert z == 0.0
    pct = compute_percentile(observed=10.0, mean=10.0, std=2.0)
    assert pytest.approx(pct, 0.1) == 50.0

    z_high = compute_z_score(observed=14.0, mean=10.0, std=2.0)
    assert z_high == 2.0
    pct_high = compute_percentile(observed=14.0, mean=10.0, std=2.0)
    assert pytest.approx(pct_high, 0.5) == 97.7
