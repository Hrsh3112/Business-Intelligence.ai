"""Stage 3 — POST /feedback. The endpoint the problem statement asks for
(Req 7), which previously did not exist at all.

The behaviour under test is mostly about failure: feedback is a side channel,
and losing a line of it must never disturb the report the user is reading.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api.config.settings import settings
from api.main import app

client = TestClient(app)


@pytest.fixture()
def log_path(tmp_path, monkeypatch):
    """Point the log at a temp file so tests never touch the real
    feedback.jsonl in the repo root."""
    path = tmp_path / "feedback.jsonl"
    monkeypatch.setattr(settings, "FEEDBACK_LOG_PATH", str(path))
    return path


def _read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestRecording:
    def test_thumbs_up_is_recorded(self, log_path):
        response = client.post("/feedback", json={"job_id": "job-1", "verdict": "useful"})
        assert response.status_code == 200
        assert response.json()["recorded"] is True

        records = _read_lines(log_path)
        assert len(records) == 1
        assert records[0]["job_id"] == "job-1"
        assert records[0]["verdict"] == "useful"

    def test_server_stamps_its_own_received_at(self, log_path):
        client.post("/feedback", json={"job_id": "job-1", "verdict": "useful"})
        record = _read_lines(log_path)[0]
        # The client's clock is not evidence; C2 stamps this itself.
        assert "received_at" in record
        assert record["received_at"].endswith("+00:00")

    def test_appends_rather_than_overwrites(self, log_path):
        client.post("/feedback", json={"job_id": "job-1", "verdict": "useful"})
        client.post("/feedback", json={"job_id": "job-2", "verdict": "not_useful"})
        records = _read_lines(log_path)
        assert [r["job_id"] for r in records] == ["job-1", "job-2"]

    def test_analyst_correction_on_a_specific_anomaly(self, log_path):
        response = client.post(
            "/feedback",
            json={
                "job_id": "job-1",
                "target": "anomaly",
                "anomaly_id": "anom_critical_churn_rate",
                "verdict": "not_useful",
                "correction": "was_noise",
                "comment": "Seasonal, we see this every January.",
            },
        )
        assert response.json()["recorded"] is True
        record = _read_lines(log_path)[0]
        assert record["correction"] == "was_noise"
        assert record["anomaly_id"] == "anom_critical_churn_rate"

    def test_creates_the_parent_directory_if_missing(self, tmp_path, monkeypatch):
        nested = tmp_path / "does" / "not" / "exist" / "feedback.jsonl"
        monkeypatch.setattr(settings, "FEEDBACK_LOG_PATH", str(nested))
        assert client.post("/feedback", json={"job_id": "j", "verdict": "useful"}).json()["recorded"] is True
        assert nested.exists()


class TestRejection:
    def test_unknown_verdict_is_rejected_not_stored(self, log_path):
        response = client.post("/feedback", json={"job_id": "job-1", "verdict": "meh"})
        assert response.status_code == 422
        assert not log_path.exists()

    def test_anomaly_target_without_an_id_is_rejected(self, log_path):
        response = client.post("/feedback", json={"job_id": "j", "target": "anomaly", "verdict": "useful"})
        assert response.status_code == 422

    def test_oversized_comment_is_rejected(self, log_path):
        # Unauthenticated writes to disk: an uncapped comment is a free
        # disk-fill, so the cap is a guard, not a formatting preference.
        response = client.post(
            "/feedback",
            json={"job_id": "j", "verdict": "useful", "comment": "x" * 2001},
        )
        assert response.status_code == 422


class TestDegradation:
    def test_unwritable_path_degrades_instead_of_500(self, tmp_path, monkeypatch):
        # Point the log at a directory: opening it for append raises OSError,
        # standing in for a full disk or a read-only volume.
        unwritable = tmp_path / "a_directory"
        unwritable.mkdir()
        monkeypatch.setattr(settings, "FEEDBACK_LOG_PATH", str(unwritable))

        response = client.post("/feedback", json={"job_id": "job-1", "verdict": "useful"})

        assert response.status_code == 200  # never a 500 on an anticipated path
        body = response.json()
        assert body["recorded"] is False
        assert "report is unaffected" in body["message"]
