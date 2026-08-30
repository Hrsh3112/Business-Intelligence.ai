"""Stage 4 — source manifest. Req 2 (heterogeneous sources, grain, freshness)
was the project's biggest gap, and the fix is entirely on C2's side of the
boundary: everything below is derived from the CompanyInput we already hold.

The tests are mostly about the declared/computed distinction. A grain or a
freshness date we computed is evidence; a source label the user typed is a
claim, and the two must never be presented as the same thing.
"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from api.config.settings import settings
from api.main import app
from api.mocks.mock_c3 import MockC3
from api.models.internal import FormMetadata
from api.models.shared import Persona
from api.orchestration import pipeline as pipeline_module
from api.orchestration.c1_adapter import adapt_company_input_for_c1
from api.orchestration.pipeline import run_pipeline
from api.parsing.builder import build_company_input
from api.parsing.ingest import ingest_csv
from api.parsing.lineage import build_source_manifest
from api.tests.fixtures.builders import FIXTURE_BUILDERS

client = TestClient(app)

CLEAN_CSV = (
    b"Month,Churn,GM\n2024-01,2.0,75.0\n2024-02,2.1,74.5\n2024-03,1.9,74.8\n"
    b"2024-04,2.2,75.1\n2024-05,2.0,74.9\n2024-06,1.8,75.3\n"
)
GAPPY_CSV = (
    b"Month,Churn\n2024-01,2.0\n2024-03,2.4\n2024-04,2.6\n2024-05,2.9\n2024-06,3.1\n2024-07,3.4\n"
)


@pytest.fixture(autouse=True)
def fast_mocks(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_C1_SLEEP_S", 0.0)
    monkeypatch.setattr(settings, "MOCK_C3_SLEEP_S", 0.0)
    monkeypatch.setattr(settings, "MOCK_SCENARIO", "critical")


def _meta(**overrides) -> str:
    base = {
        "company_name": "Acme Co",
        "sector_id": "TECH_SAAS",
        "employee_count": 40,
        "region": "US",
        "annual_revenue": 4_000_000,
    }
    base.update(overrides)
    return json.dumps(base)


def _upload(csv_bytes=CLEAN_CSV, metadata=None, filename="data.csv", headers=None):
    meta_str = metadata or _meta()
    if headers is None:
        meta_dict = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
        persona = meta_dict.get("persona", "executive")
        key = "exec-demo-key" if persona == "executive" else "analyst-demo-key"
        headers = {"X-Api-Key": key}
    return client.post(
        "/analyze/upload",
        files={"file": (filename, csv_bytes, "text/csv")},
        data={"metadata": meta_str},
        headers=headers,
    )


class TestComputedFacts:
    """Grain, coverage and interpolation are measured from the submitted data."""

    def test_grain_and_period_range_come_from_the_data(self):
        company_input, _ = FIXTURE_BUILDERS["critical"]()
        manifest = build_source_manifest(company_input)
        churn = next(m for m in manifest if m.metric_id == "churn_rate")
        assert churn.grain == "monthly"
        assert churn.first_period == "2024-01"
        assert churn.as_of_period == "2024-08"  # freshness, not a guess
        assert churn.points == 8

    def test_interpolated_points_are_counted_not_hidden(self):
        body = _upload(GAPPY_CSV).json()
        churn = next(m for m in body["source_manifest"] if m["metric_id"] == "churn_rate")
        # C2 gap-filled 2024-02; the manifest must admit it rather than
        # presenting 7 points as if all 7 were observed.
        assert churn["interpolated_points"] == 1
        assert churn["points"] > churn["interpolated_points"]

    def test_confidence_is_carried_through(self):
        body = _upload().json()
        assert all(m["confidence"] == 0.9 for m in body["source_manifest"])  # clean CSV


class TestDeclaredVsInferred:
    """source_system is a claim, and source_basis says whose."""

    def test_declared_source_is_marked_declared(self):
        body = _upload(metadata=_meta(source_system="ERP export (monthly)")).json()
        assert all(m["source_system"] == "ERP export (monthly)" for m in body["source_manifest"])
        assert all(m["source_basis"] == "declared" for m in body["source_manifest"])

    def test_undeclared_source_falls_back_to_the_filename_and_says_so(self):
        body = _upload(filename="q3_actuals.csv").json()
        entry = body["source_manifest"][0]
        assert entry["source_system"] == "q3_actuals.csv"
        # Never "declared": nobody told us this, we just know what we were handed.
        assert entry["source_basis"] == "upload_filename"

    def test_per_metric_sources_support_two_systems_in_one_submission(self):
        # The multi-source scenario, honestly: two declared systems at two
        # cadences, without pretending we hold a live connector to either.
        metadata = _meta(
            source_system="ERP export (monthly)",
            metric_sources={"churn_rate": "CRM export (daily)"},
        )
        manifest = {m["metric_id"]: m for m in _upload(metadata=metadata).json()["source_manifest"]}
        assert manifest["churn_rate"]["source_system"] == "CRM export (daily)"
        assert manifest["gross_margin"]["source_system"] == "ERP export (monthly)"
        assert len({m["source_system"] for m in manifest.values()}) == 2

    def test_direct_analyze_has_no_form_metadata_so_source_is_unknown(self):
        company_input, _ = FIXTURE_BUILDERS["critical"]()
        response = client.post(
            "/analyze",
            json=company_input.model_dump(mode="json", by_alias=True),
            headers={"X-Api-Key": "analyst-demo-key"},
        )
        manifest = response.json()["source_manifest"]
        assert len(manifest) > 0  # computed facts still present
        assert all(m["source_system"] is None for m in manifest)
        assert all(m["source_basis"] == "unknown" for m in manifest)
        assert all(m["grain"] == "monthly" for m in manifest)


class TestEdges:
    """The manifest describes what was analysed, not everything in the file."""

    def test_no_input_yields_an_empty_manifest_not_a_crash(self):
        assert build_source_manifest(None) == []

    def test_excluded_metrics_are_absent_from_the_manifest(self):
        # Every column fraction-encoded: nothing survives validation, so there
        # is nothing to describe. The reasons live in warnings instead.
        fractions = b"Month,Churn,GM\n2024-01,0.020,0.750\n2024-02,0.021,0.745\n2024-03,0.019,0.748\n"
        body = _upload(fractions).json()
        assert body["error"] == "NO_USABLE_METRICS"
        assert body["source_manifest"] == []


class TestPersona:
    """Persona selects what a reader is shown. It must never reach C1 or C3,
    and must never change a computed value."""

    def test_persona_is_echoed_back(self):
        body = _upload(metadata=_meta(persona="analyst")).json()
        assert body["persona"] == "analyst"

    def test_defaults_to_executive_when_not_declared(self):
        assert _upload().json()["persona"] == "executive"

    def test_direct_analyze_has_no_form_metadata_so_defaults_apply(self):
        company_input, _ = FIXTURE_BUILDERS["critical"]()
        response = client.post(
            "/analyze",
            json=company_input.model_dump(mode="json", by_alias=True),
            headers={"X-Api-Key": "exec-demo-key"},
        )
        assert response.json()["persona"] == "executive"

    def test_persona_changes_nothing_that_was_computed(self):
        # The guarantee that makes persona safe: same submission, same numbers.
        # Field redaction differs server-side, but computed metrics/health match.
        exec_body = _upload(metadata=_meta(persona="executive")).json()
        analyst_body = _upload(metadata=_meta(persona="analyst")).json()

        def signature(body):
            report = body["result"]["anomaly_report"]
            return (
                report["overall_health_score"],
                [(a["anomaly_id"], a["severity_score"]) for a in report["anomalies"]],
                [(m["metric_id"], m["points"], m["grain"]) for m in body["source_manifest"]],
            )

        assert signature(exec_body) == signature(analyst_body)


class TestPersonaReachesC3:
    """The transport chain for the one field C2 added to the shared schema.

    Each hop is pinned because the chain is non-obvious: persona rides inside
    CompanyInput, is DROPPED by C1's own schema, and is re-attached by the
    pipeline so C3 can see it. Break any hop and the failure is silent.
    """

    def test_persona_travels_on_company_input(self):
        table = ingest_csv(CLEAN_CSV, "clean.csv")
        form = FormMetadata.model_validate_json(_meta(persona="analyst"))
        result = build_company_input(table, form)
        assert result.company_input.persona == Persona.ANALYST

    def test_c1_adapter_drops_it_without_raising(self):
        # The safety argument for touching shared.py: ml_engine's CompanyInput
        # sets no model_config, so extra="ignore" applies and C1 never sees
        # this field. If C1 ever switches to extra="forbid", this test is where
        # it surfaces instead of at the demo.
        company_input, _ = FIXTURE_BUILDERS["critical"]()
        with_persona = company_input.model_copy(update={"persona": Persona.ANALYST})
        adapted = adapt_company_input_for_c1(with_persona)
        assert adapted is not None

    def test_pipeline_attaches_persona_to_the_report_handed_to_c3(self):
        company_input, _ = FIXTURE_BUILDERS["critical"]()
        with_persona = company_input.model_copy(update={"persona": Persona.ANALYST})

        seen = {}

        def _capture_c3():
            def _enrich(report):
                seen["persona"] = getattr(report, "persona", None)
                return MockC3(sleep_s=0).enrich_report(report)

            return _enrich

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(settings, "MOCK_SCENARIO", "critical")
            mp.setattr(pipeline_module, "get_c3", _capture_c3)
            asyncio.run(run_pipeline(with_persona))

        # What C3 would read today if it looked. It does not look yet.
        assert seen["persona"] == "analyst"

    def test_absent_persona_leaves_the_report_untouched(self):
        company_input, _ = FIXTURE_BUILDERS["critical"]()
        assert company_input.persona is None
        response = asyncio.run(run_pipeline(company_input))
        assert getattr(response.result.anomaly_report, "persona", None) is None
