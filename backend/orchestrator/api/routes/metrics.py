"""GET /metrics/{sector_id} — the canonical metric catalog for a sector.

Named in the locked API surface from the start and never built until now. It
matters for one reason beyond convenience: the problem statement asks for a
lightweight KPI/semantic contract, and until this existed the only such
artifact was prose in a document. This serves the same facts from
`metric_config.yaml` at runtime, so the contract is discoverable by a machine
and cannot drift from what the parser actually enforces — both read the one
YAML.

Free, side-effect-free, and never touches C1 or C3.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.config.loader import metrics as load_metrics
from api.config.loader import thresholds as load_thresholds
from api.models.internal import MetricCatalogEntry, MetricCatalogResponse
from api.models.shared import SectorId

router = APIRouter()


_METRIC_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "monthly_recurring_revenue_growth": {
        "description": "Month-over-month growth rate in recurring subscription revenue.",
        "calculation_formula": "(MRR_t - MRR_{t-1}) / MRR_{t-1} * 100",
    },
    "churn_rate": {
        "description": "Monthly customer or revenue attrition rate.",
        "calculation_formula": "(Lost_Customers_t / Active_Customers_{t-1}) * 100",
    },
    "customer_acquisition_cost": {
        "description": "Fully loaded sales and marketing cost to acquire a single customer.",
        "calculation_formula": "Total_Sales_Marketing_Spend_t / New_Customers_Acquired_t",
    },
    "lifetime_value": {
        "description": "Estimated gross customer lifetime economic value.",
        "calculation_formula": "(ARPU * Gross_Margin_Pct) / Churn_Rate_Pct",
    },
    "net_revenue_retention": {
        "description": "Expansion revenue minus contraction and churn from existing customer cohort.",
        "calculation_formula": "((Starting_ARR + Expansion - Contraction - Churn) / Starting_ARR) * 100",
    },
    "burn_rate": {
        "description": "Net monthly cash outflow across operations.",
        "calculation_formula": "Cash_Start_Period - Cash_End_Period",
    },
    "gross_margin": {
        "description": "Gross profit generated as a percentage of total revenue.",
        "calculation_formula": "((Revenue - COGS) / Revenue) * 100",
    },
    "inventory_turnover": {
        "description": "Number of times inventory is sold and replaced over a defined period.",
        "calculation_formula": "Cost_of_Goods_Sold / Average_Inventory",
    },
    "average_order_value": {
        "description": "Average dollar amount spent each time a customer places an order.",
        "calculation_formula": "Total_Revenue / Total_Orders",
    },
    "sales_per_square_foot": {
        "description": "Total sales generated per square foot of retail store area.",
        "calculation_formula": "Total_Store_Sales / Total_Square_Footage",
    },
    "return_rate": {
        "description": "Percentage of sold items returned by customers.",
        "calculation_formula": "(Returned_Units / Total_Units_Sold) * 100",
    },
    "same_store_sales_growth": {
        "description": "Year-over-year revenue growth from stores operating for at least one year.",
        "calculation_formula": "((Comp_Sales_t - Comp_Sales_{t-1}) / Comp_Sales_{t-1}) * 100",
    },
    "sell_through_rate": {
        "description": "Percentage of inventory received that was sold during the period.",
        "calculation_formula": "(Units_Sold / Units_Received) * 100",
    },
}


@router.get("/metrics/{sector_id}", response_model=MetricCatalogResponse)
async def metric_catalog(sector_id: str):
    """`sector_id` is accepted case-insensitively; TECH_SAAS and RETAIL are the
    only sectors in MVP scope."""
    normalized = sector_id.strip().upper()
    valid = [s.value for s in SectorId]
    if normalized not in valid:
        # A plain 404 naming the valid values, rather than routing an unknown
        # path segment through the ApiResponse envelope — this endpoint is not
        # a pipeline run and should not answer like one.
        return JSONResponse(
            status_code=404,
            content={
                "error": "UNKNOWN_SECTOR",
                "message": f"'{sector_id}' is not a known sector.",
                "valid_sectors": valid,
            },
        )

    correlation_matrix: dict[str, dict[str, float]] = {}
    try:
        from ml_engine.config.loader import load_sector_config
        sector_cfg = load_sector_config(normalized)
        correlation_matrix = sector_cfg.correlation_matrix
    except Exception:
        correlation_matrix = {}

    entries = []
    for metric_id, config in sorted(load_metrics().items()):
        if normalized not in config.get("sector_ids", []):
            continue

        metric_corrs = correlation_matrix.get(metric_id, {})
        drivers = [other_id for other_id, corr_val in metric_corrs.items() if abs(corr_val) >= 0.5]
        desc_info = _METRIC_DESCRIPTIONS.get(metric_id, {})

        entries.append(
            MetricCatalogEntry(
                metric_id=metric_id,
                display_name=config["display_name"],
                unit=config["unit"],
                category=config["category"],
                direction=config["direction"],
                valid_min=config.get("valid_min"),
                valid_max=config.get("valid_max"),
                accepted_aliases=config.get("common_aliases", []),
                description=desc_info.get("description"),
                calculation_formula=desc_info.get("calculation_formula"),
                drivers=drivers,
                lineage={
                    "supported_sources": ["CRM", "ERP", "Billing", "Analytics", "Manual CSV"],
                    "cadence": "monthly (or daily downsampled to monthly)",
                },
                access_restrictions={
                    "executive": "redacted_statistical_fields (z_score, noise_confidence, slope, acceleration, driver_rank)",
                    "analyst": "full_diagnostic_access",
                },
            )
        )

    return MetricCatalogResponse(
        sector_id=normalized,
        metric_count=len(entries),
        metrics=entries,
        min_periods=load_thresholds().get("min_periods", {}),
        correlation_matrix=correlation_matrix,
        access_entitlements={
            "executive": {
                "allowed_views": ["business_summary", "anomaly_cards", "prescriptions", "highlights"],
                "redacted_fields": ["z_score", "noise_confidence", "slope", "acceleration", "driver_rank"],
            },
            "analyst": {
                "allowed_views": ["business_summary", "anomaly_cards", "prescriptions", "highlights", "statistical_diagnostics"],
                "redacted_fields": [],
            },
        },
        lineage_manifest_spec={
            "supported_source_systems": ["CRM", "ERP", "Billing", "Analytics", "Manual CSV"],
            "cadences": ["daily", "monthly", "quarterly", "annual"],
            "grain_reconciliation": "Daily-grain series are downsampled via arithmetic mean to monthly grain before statistical comparison.",
        },
    )
