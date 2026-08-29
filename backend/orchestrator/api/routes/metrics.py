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

    entries = [
        MetricCatalogEntry(
            metric_id=metric_id,
            display_name=config["display_name"],
            unit=config["unit"],
            category=config["category"],
            direction=config["direction"],
            valid_min=config.get("valid_min"),
            valid_max=config.get("valid_max"),
            accepted_aliases=config.get("common_aliases", []),
        )
        for metric_id, config in sorted(load_metrics().items())
        if normalized in config.get("sector_ids", [])
    ]

    return MetricCatalogResponse(
        sector_id=normalized,
        metric_count=len(entries),
        metrics=entries,
        min_periods=load_thresholds().get("min_periods", {}),
    )
