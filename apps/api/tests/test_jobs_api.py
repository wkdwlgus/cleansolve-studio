from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cleansolve_api.main import app
from cleansolve_api.routes.jobs import _jobs
from cleansolve_api.settings import Settings


@pytest.fixture(autouse=True)
def clear_jobs():
    _jobs.clear()
    yield
    _jobs.clear()


def test_create_job_and_run_mock_workflow():
    client = TestClient(app)

    create_response = client.post("/jobs")
    job_id = create_response.json()["job_id"]
    run_response = client.post(f"/jobs/{job_id}/run")

    assert create_response.status_code == 201
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "APPROVED"
    assert run_response.json()["revision_attempts"] == 1


def test_review_items_endpoint_hides_internal_needs_review_items():
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    client.post(f"/jobs/{job_id}/run")
    response = client.get(f"/jobs/{job_id}/review-items")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_get_unknown_job_returns_404():
    client = TestClient(app)

    response = client.get("/jobs/job_unknown")

    assert response.status_code == 404


def test_run_unknown_job_returns_404():
    client = TestClient(app)

    response = client.post("/jobs/job_unknown/run")

    assert response.status_code == 404


def test_get_unknown_job_review_items_returns_404():
    client = TestClient(app)

    response = client.get("/jobs/job_unknown/review-items")

    assert response.status_code == 404


def test_review_items_endpoint_is_empty_before_running_workflow():
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    response = client.get(f"/jobs/{job_id}/review-items")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_settings_use_cleansolve_storage_root(monkeypatch):
    monkeypatch.delenv("STORAGE_ROOT", raising=False)
    monkeypatch.setenv("CLEANSOLVE_STORAGE_ROOT", "var/custom-jobs")

    settings = Settings()

    assert settings.storage_root == Path("var/custom-jobs")
