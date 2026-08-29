"""One-off script: dumps a full ApiResponse JSON per demo scenario, using the
existing fixture builders + mocks directly (no HTTP round trip, no server
restart needed). Feeds the frontend's scenario switcher (Phase3-Plan T3.8) —
"No new backend endpoints" rules out a live runtime-scenario endpoint, so the
switcher swaps between the real API and these static snapshots instead.

Run from the project root:
    ./.venv/Scripts/python.exe scripts/dump_scenario_responses.py
"""

import json
import uuid
from pathlib import Path

from api.config.pricing import estimate_cost
from api.mocks.mock_c3 import MockC3
from api.models.internal import ApiResponse, FormMetadata, Timings
from api.orchestration.degradation import wrap_bare_report
from api.parsing.lineage import build_source_manifest
from api.tests.fixtures.builders import FIXTURE_BUILDERS

OUT_DIR = Path(__file__).parent.parent / "web" / "src" / "lib" / "scenario-fixtures"


def build_response(scenario: str) -> ApiResponse:
    company_input, report = FIXTURE_BUILDERS[scenario]()

    # The demo scenarios stand in for a two-system submission: churn comes from
    # the CRM, everything else from the ERP export. Declared, not inferred —
    # the same thing a user types into the form, so the snapshots show exactly
    # what a real submission would.
    demo_metadata = FormMetadata(
        company_name=company_input.company_metadata.name,
        sector_id=company_input.sector_id,
        employee_count=company_input.company_metadata.employee_count,
        region=company_input.company_metadata.region,
        revenue_band=company_input.company_metadata.revenue_band,
        source_system="ERP export (monthly)",
        metric_sources={"churn_rate": "CRM export (daily rollup)"},
    )
    manifest = build_source_manifest(company_input, demo_metadata)

    # These snapshots bypass run_pipeline(), so anything the pipeline derives
    # has to be derived here too or the offline demo silently loses it — as
    # happened with `cost` when telemetry landed. Call the same estimator the
    # pipeline calls; never hand-write the numbers.
    if report.refusal is not None:
        enriched = wrap_bare_report(report, degraded=False, reason=None)
        return ApiResponse(
            job_id=str(uuid.uuid4()),
            status="refused",
            result=enriched,
            timings=Timings(c1_ms=200, c3_ms=None, total_ms=205),
            cost=estimate_cost(None, None),
            source_manifest=manifest,
        )

    fail_llm = scenario == "degraded"
    c3 = MockC3(fail_llm=fail_llm, sleep_s=0)
    enriched = c3.enrich_report(report)
    return ApiResponse(
        job_id=str(uuid.uuid4()),
        status="complete",
        result=enriched,
        timings=Timings(c1_ms=200, c3_ms=1500, total_ms=1700),
        cost=estimate_cost(enriched.metadata.llm_model, enriched.metadata.llm_tokens_used),
        source_manifest=manifest,
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for scenario in FIXTURE_BUILDERS:
        response = build_response(scenario)
        out_path = OUT_DIR / f"{scenario}.json"
        out_path.write_text(
            json.dumps(response.model_dump(mode="json", by_alias=True), indent=2), encoding="utf-8"
        )
        print(f"wrote {out_path.relative_to(Path(__file__).parent.parent)}")


if __name__ == "__main__":
    main()
