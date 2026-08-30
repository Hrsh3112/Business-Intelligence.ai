"""T1.5 / T1.7 — POST /analyze over the real FastAPI app, and exit criterion 6:
no code path anywhere returns HTTP 500."""

import pytest
from fastapi.testclient import TestClient

from api.config.settings import settings
from api.main import app
from api.tests.fixtures.builders import FIXTURE_BUILDERS

client = TestClient(app, headers={"X-Api-Key": "analyst-demo-key"})


@pytest.fixture(autouse=True)
def fast_and_clean_mocks(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_C1_SLEEP_S", 0.0)
    monkeypatch.setattr(settings, "MOCK_C3_SLEEP_S", 0.0)
    monkeypatch.setattr(settings, "MOCK_C1_RAISE_ON_CALL", False)
    monkeypatch.setattr(settings, "MOCK_C3_RAISE_ON_CALL", False)
    monkeypatch.setattr(settings, "MOCK_C3_FAIL_LLM", False)
    monkeypatch.setattr(settings, "MOCK_SCENARIO", "critical")
    monkeypatch.setattr(settings, "C1_TIMEOUT_S", 10.0)
    monkeypatch.setattr(settings, "C3_TIMEOUT_S", 30.0)


def _valid_body() -> dict:
    company_input, _ = FIXTURE_BUILDERS["critical"]()
    return company_input.model_dump(mode="json", by_alias=True)


def test_valid_body_returns_200_complete():
    response = client.post("/analyze", json=_valid_body())
    assert response.status_code == 200
    body = response.json()
    # Name the failure rather than just reporting "not complete". This test has
    # been seen to fail on a heavily loaded machine (a run 4-13x slower than
    # normal), and a bare status assertion gave no way to tell a C1_TIMEOUT
    # from anything else. If it trips again, the message says which.
    assert body["status"] == "complete", f"error={body.get('error')} timings={body.get('timings')}"
    assert body["result"]["narrative"] is not None


def test_malformed_body_returns_422_in_our_envelope():
    response = client.post("/analyze", json={"company_id": "only-this-field"})
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == "VALIDATION_ERROR"
    assert len(body["warnings"]) > 0
    assert body["warnings"][0]["code"] == "SCHEMA_VALIDATION_ERROR"


def test_unknown_sector_id_returns_clean_validation_error():
    payload = _valid_body()
    payload["sector_id"] = "NOT_A_REAL_SECTOR"
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"MOCK_SCENARIO": "refusal"},
        {"MOCK_C1_RAISE_ON_CALL": True},
        {"MOCK_C3_RAISE_ON_CALL": True},
        {"MOCK_C3_FAIL_LLM": True},
    ],
)
def test_no_failure_injection_ever_returns_http_500(monkeypatch, overrides):
    for key, value in overrides.items():
        monkeypatch.setattr(settings, key, value)

    if overrides.get("MOCK_SCENARIO") == "refusal":
        company_input, _ = FIXTURE_BUILDERS["refusal"]()
        body = company_input.model_dump(mode="json", by_alias=True)
    else:
        body = _valid_body()

    response = client.post("/analyze", json=body)
    assert response.status_code != 500


def test_malformed_json_body_also_never_returns_500():
    response = client.post("/analyze", json={"garbage": True})
    assert response.status_code != 500


def test_missing_api_key_returns_401():
    unauthed_client = TestClient(app)
    response = unauthed_client.post("/analyze", json=_valid_body())
    assert response.status_code == 401


def test_invalid_api_key_returns_401():
    bad_client = TestClient(app, headers={"X-Api-Key": "invalid-key"})
    response = bad_client.post("/analyze", json=_valid_body())
    assert response.status_code == 401


def test_exec_api_key_redacts_analyst_fields():
    exec_client = TestClient(app, headers={"X-Api-Key": "exec-demo-key"})
    response = exec_client.post("/analyze", json=_valid_body())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["persona"] == "executive"
    if body["result"] and body["result"]["anomaly_report"]["anomalies"]:
        for anom in body["result"]["anomaly_report"]["anomalies"]:
            assert "z_score" not in anom["deviation"] or anom["deviation"]["z_score"] is None
            assert "noise_confidence" not in anom or anom["noise_confidence"] is None
            assert "slope" not in anom["trend"] or anom["trend"]["slope"] is None
            assert "acceleration" not in anom["trend"] or anom["trend"]["acceleration"] is None


def test_analyst_api_key_preserves_analyst_fields():
    analyst_client = TestClient(app, headers={"X-Api-Key": "analyst-demo-key"})
    response = analyst_client.post("/analyze", json=_valid_body())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["persona"] == "analyst"
    if body["result"] and body["result"]["anomaly_report"]["anomalies"]:
        anom = body["result"]["anomaly_report"]["anomalies"][0]
        assert anom["deviation"]["z_score"] is not None
        assert anom["noise_confidence"] is not None


def test_daily_grain_downsampling_and_warning():
    payload = _valid_body()
    # Add daily grain points for the first metric
    payload["metrics"][0]["grain"] = "daily"
    payload["metrics"][0]["values"] = [
        {"period": "2026-01-05", "value": 2.0},
        {"period": "2026-01-20", "value": 4.0},
        {"period": "2026-02-05", "value": 6.0},
        {"period": "2026-02-20", "value": 8.0},
        {"period": "2026-03-05", "value": 1.0},
        {"period": "2026-03-20", "value": 3.0},
        {"period": "2026-04-05", "value": 2.0},
        {"period": "2026-04-20", "value": 4.0},
        {"period": "2026-05-05", "value": 5.0},
        {"period": "2026-05-20", "value": 7.0},
        {"period": "2026-06-05", "value": 6.0},
        {"period": "2026-06-20", "value": 8.0},
    ]
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    # Check that grain mismatch warning was generated
    warning_msgs = [w["message"] for w in body.get("warnings", [])]
    assert any("downsampled to monthly grain" in msg for msg in warning_msgs)


def test_multisource_crm_fixture_ingestion():
    """Verify that data/crm_fixture.json can be loaded as a daily-grain source and analyzed alongside ERP metrics."""
    import json
    from pathlib import Path

    crm_path = Path(__file__).resolve().parents[4] / "data" / "crm_fixture.json"
    assert crm_path.exists(), f"CRM fixture file not found at {crm_path}"

    with open(crm_path, "r", encoding="utf-8") as f:
        crm_data = json.load(f)

    # Build multi-source payload combining CRM daily metrics and ERP monthly metrics
    metrics = []
    for m_id, points in crm_data["metrics"].items():
        metrics.append({
            "metric_id": m_id,
            "granularity": "monthly",
            "grain": crm_data["grain"],
            "source_system": crm_data["source_system"],
            "data_as_of": crm_data["data_as_of"],
            "confidence": 1.0,
            "values": points,
        })

    # Add monthly ERP metric
    monthly_periods = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    metrics.append({
        "metric_id": "gross_margin",
        "granularity": "monthly",
        "source_system": "ERP",
        "confidence": 1.0,
        "values": [{"period": p, "value": 75.0} for p in monthly_periods],
    })

    payload = {
        "company_id": "comp_multisource_demo",
        "sector_id": "TECH_SAAS",
        "reporting_period": {"type": "monthly", "start": "2026-01-01", "end": "2026-06-30"},
        "company_metadata": {
            "name": "Multi-Source SaaS Corp",
            "revenue_band": "1M-10M",
            "employee_count": 60,
            "region": "US",
        },
        "metrics": metrics,
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    # Verify downsampling warning was generated for the daily CRM data
    warning_msgs = [w["message"] for w in body.get("warnings", [])]
    assert any("downsampled to monthly grain" in msg for msg in warning_msgs)
    assert any("CRM" in msg for msg in warning_msgs)
    # Verify manifest reflects both CRM and ERP sources
    sources = {m["metric_id"]: m["source_system"] for m in body.get("source_manifest", [])}
    assert sources.get("churn_rate") == "CRM"
    assert sources.get("customer_acquisition_cost") == "CRM"
    assert sources.get("gross_margin") == "ERP"




