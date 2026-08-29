"""T2.7 — POST /analyze/upload. Exit criterion 13."""

import json

import pytest
from fastapi.testclient import TestClient

from api.config.settings import settings
from api.main import app

client = TestClient(app)

VALID_METADATA = json.dumps(
    {
        "company_name": "Acme Co",
        "sector_id": "TECH_SAAS",
        "employee_count": 40,
        "region": "US",
        "annual_revenue": 4_000_000,
    }
)

CLEAN_CSV = b"Month,Churn,GM\n2024-01,2.0,75.0\n2024-02,2.1,74.5\n2024-03,1.9,74.8\n2024-04,2.2,75.1\n2024-05,2.0,74.9\n2024-06,1.8,75.3\n"
UNKNOWN_COL_CSV = b"Month,Churn,Nonsense Column\n2024-01,2.0,1\n2024-02,2.1,2\n2024-03,1.9,3\n2024-04,2.2,4\n2024-05,2.0,5\n2024-06,1.8,6\n"
GARBAGE = b"not a spreadsheet\njust some prose\nnothing tabular\n"
# Every percentage fraction-encoded: both columns get excluded by the
# distributional unit check, leaving nothing to analyse.
ALL_EXCLUDED_CSV = b"Month,Churn,GM\n2024-01,0.020,0.750\n2024-02,0.021,0.745\n2024-03,0.019,0.748\n2024-04,0.022,0.751\n2024-05,0.020,0.749\n2024-06,0.018,0.753\n"
# Nothing resolves to a known metric at all.
NOTHING_RESOLVES_CSV = b"Month,Foo,Bar\n2024-01,1,2\n2024-02,3,4\n2024-03,5,6\n2024-04,7,8\n2024-05,9,10\n2024-06,11,12\n"


@pytest.fixture(autouse=True)
def fast_mocks(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_C1_SLEEP_S", 0.0)
    monkeypatch.setattr(settings, "MOCK_C3_SLEEP_S", 0.0)
    monkeypatch.setattr(settings, "MOCK_SCENARIO", "critical")


def _post_upload(csv_bytes: bytes, metadata: str = VALID_METADATA, mapping_overrides: str | None = None):
    data = {"metadata": metadata}
    if mapping_overrides is not None:
        data["mapping_overrides"] = mapping_overrides
    return client.post(
        "/analyze/upload",
        files={"file": ("data.csv", csv_bytes, "text/csv")},
        data=data,
    )


def test_clean_csv_runs_full_pipeline():
    response = _post_upload(CLEAN_CSV)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["result"]["narrative"] is not None


def test_garbage_never_starts_pipeline():
    response = _post_upload(GARBAGE)
    assert response.status_code != 500
    body = response.json()
    assert body["status"] == "failed"
    assert body["result"] is None


def test_parse_warnings_survive_onto_final_response():
    response = _post_upload(UNKNOWN_COL_CSV)
    body = response.json()
    assert body["status"] == "complete"
    codes = {w["code"] for w in body["warnings"]}
    assert "UNKNOWN_METRIC" in codes


def test_mapping_override_resolves_otherwise_unknown_column():
    overrides = json.dumps({"Nonsense Column": "gross_margin"})
    response = _post_upload(UNKNOWN_COL_CSV, mapping_overrides=overrides)
    body = response.json()
    assert body["status"] == "complete"
    codes = {w["code"] for w in body["warnings"]}
    assert "UNKNOWN_METRIC" not in codes


class TestNoUsableMetrics:
    """C2 must never hand C1 an empty metrics list. C1 would answer
    NO_METRICS_SUBMITTED, which is false — the user did submit data and C2
    discarded it — and the real reasons would never reach the user."""

    def test_all_metrics_excluded_blocks_with_its_own_error_code(self):
        response = _post_upload(ALL_EXCLUDED_CSV)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert body["error"] == "NO_USABLE_METRICS"
        assert body["result"] is None

    def test_exclusion_reasons_reach_the_user(self):
        body = _post_upload(ALL_EXCLUDED_CSV).json()
        codes = {w["code"] for w in body["warnings"]}
        # The specific "why", not just the fact that something went wrong.
        assert "UNIT_SCALE_SUSPECT" in codes
        assert any("nothing left to analyse" in w["message"] for w in body["warnings"])

    def test_nothing_resolving_is_also_blocked_not_dispatched(self):
        body = _post_upload(NOTHING_RESOLVES_CSV).json()
        assert body["status"] == "failed"
        assert body["error"] == "NO_USABLE_METRICS"
        assert any("matched a metric we recognise" in w["message"] for w in body["warnings"])

    def test_partial_exclusion_still_analyses_the_survivors(self):
        # The guard must block only when *nothing* survives — one usable
        # column is still a real analysis.
        body = _post_upload(UNKNOWN_COL_CSV).json()
        assert body["status"] == "complete"


