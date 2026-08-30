"""P2 — GET /metrics/{sector_id}, and the CORS default.

The endpoint was in the locked API surface from the start and never built. It
matters beyond convenience: it turns metric_config.yaml into a machine-readable
KPI/semantic contract served at runtime, so what the API advertises and what
the parser enforces are the same file.
"""

import pytest
from fastapi.testclient import TestClient

from api.config.loader import metrics as load_metrics
from api.config.settings import settings
from api.main import app

client = TestClient(app)


class TestCatalog:
    def test_tech_saas_returns_its_seven_metrics(self):
        body = client.get("/metrics/TECH_SAAS").json()
        assert body["sector_id"] == "TECH_SAAS"
        assert body["metric_count"] == 7
        assert len(body["metrics"]) == 7

    def test_retail_returns_its_eight_metrics(self):
        body = client.get("/metrics/RETAIL").json()
        assert body["metric_count"] == 8

    def test_sector_id_is_case_insensitive(self):
        assert client.get("/metrics/tech_saas").json()["sector_id"] == "TECH_SAAS"

    def test_entries_carry_what_a_caller_needs_to_build_a_valid_csv(self):
        body = client.get("/metrics/TECH_SAAS").json()
        churn = next(m for m in body["metrics"] if m["metric_id"] == "churn_rate")
        assert churn["display_name"] == "Churn Rate (%)"
        assert churn["unit"] == "percentage"
        assert churn["direction"] == "lower_is_better"
        # Publishing the alias table is the point: without it a caller
        # discovers what resolves by trial and error.
        assert "Churn" in churn["accepted_aliases"]

    def test_advertised_bounds_match_the_config_the_parser_enforces(self):
        # The guarantee that makes this a contract rather than documentation:
        # one YAML feeds both the endpoint and the validation layer.
        catalog = {m["metric_id"]: m for m in client.get("/metrics/TECH_SAAS").json()["metrics"]}
        config = load_metrics()
        for metric_id, entry in catalog.items():
            assert entry["valid_min"] == config[metric_id]["valid_min"]
            assert entry["valid_max"] == config[metric_id]["valid_max"]

    def test_min_periods_are_published_too(self):
        body = client.get("/metrics/TECH_SAAS").json()
        assert body["min_periods"]["monthly"]["hard_block"] == 3

    def test_shared_metrics_appear_in_both_sectors(self):
        saas = {m["metric_id"] for m in client.get("/metrics/TECH_SAAS").json()["metrics"]}
        retail = {m["metric_id"] for m in client.get("/metrics/RETAIL").json()["metrics"]}
        assert {"gross_margin", "customer_acquisition_cost"} <= (saas & retail)

    def test_drivers_and_correlation_matrix_published(self):
        body = client.get("/metrics/TECH_SAAS").json()
        assert "correlation_matrix" in body
        assert body["correlation_matrix"] is not None
        assert "churn_rate" in body["correlation_matrix"]
        churn = next(m for m in body["metrics"] if m["metric_id"] == "churn_rate")
        assert "drivers" in churn
        assert "net_revenue_retention" in churn["drivers"]

    def test_access_restrictions_and_lineage_published(self):
        body = client.get("/metrics/TECH_SAAS").json()
        assert "access_entitlements" in body
        assert "executive" in body["access_entitlements"]
        assert "analyst" in body["access_entitlements"]
        assert "z_score" in body["access_entitlements"]["executive"]["redacted_fields"]
        assert "lineage_manifest_spec" in body
        churn = next(m for m in body["metrics"] if m["metric_id"] == "churn_rate")
        assert churn["lineage"] is not None
        assert "CRM" in churn["lineage"]["supported_sources"]

    def test_descriptions_and_formulas_published(self):
        body = client.get("/metrics/TECH_SAAS").json()
        churn = next(m for m in body["metrics"] if m["metric_id"] == "churn_rate")
        assert churn["description"] is not None
        assert churn["calculation_formula"] is not None
        assert "Lost_Customers" in churn["calculation_formula"]


class TestUnknownSector:
    def test_unknown_sector_is_a_clean_404_naming_the_valid_ones(self):
        response = client.get("/metrics/NOT_A_SECTOR")
        assert response.status_code == 404
        body = response.json()
        assert body["error"] == "UNKNOWN_SECTOR"
        assert set(body["valid_sectors"]) == {"TECH_SAAS", "RETAIL"}

    def test_out_of_scope_sector_is_rejected_not_empty(self):
        # MFG is explicitly out of MVP scope. It must 404, not return an empty
        # catalog that reads like "we support it, you just have no metrics".
        assert client.get("/metrics/MFG").status_code == 404


class TestCorsDefault:
    def test_default_is_the_local_frontend_not_a_wildcard(self):
        assert "*" not in settings.cors_allow_origins
        assert "http://localhost:3000" in settings.cors_allow_origins

    def test_wildcard_is_still_reachable_when_deliberately_set(self, monkeypatch):
        monkeypatch.setattr(settings, "CORS_ALLOW_ORIGINS", "*")
        assert settings.cors_allow_origins == ["*"]

    def test_origins_parse_with_whitespace(self, monkeypatch):
        monkeypatch.setattr(settings, "CORS_ALLOW_ORIGINS", "http://a.com , http://b.com ,")
        assert settings.cors_allow_origins == ["http://a.com", "http://b.com"]

    def test_allowed_origin_gets_the_cors_header(self):
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_disallowed_origin_gets_no_cors_header(self):
        response = client.get("/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in response.headers
        assert response.status_code == 200  # the API still answers; the browser blocks
