"""Cross-metric financial and operational ratio computations."""

from typing import Dict, Optional


class RatioCalculator:
    """Computes derived cross-metric ratios from raw feature sets."""

    @staticmethod
    def compute_ltv_cac(ltv: Optional[float], cac: Optional[float]) -> Optional[float]:
        """Compute LTV / CAC ratio."""
        if ltv is None or cac is None or cac <= 0:
            return None
        return round(ltv / cac, 2)

    @staticmethod
    def compute_revenue_per_employee(
        annual_revenue: Optional[float],
        employee_count: Optional[int]
    ) -> Optional[float]:
        """Compute annual revenue per employee."""
        if annual_revenue is None or employee_count is None or employee_count <= 0:
            return None
        return round(annual_revenue / employee_count, 2)

    @staticmethod
    def compute_burn_multiple(
        annual_burn: Optional[float],
        net_new_arr: Optional[float]
    ) -> Optional[float]:
        """Compute Burn Multiple = Annual Net Burn / Net New ARR."""
        if annual_burn is None or net_new_arr is None or net_new_arr <= 0:
            return None
        return round(annual_burn / net_new_arr, 2)
