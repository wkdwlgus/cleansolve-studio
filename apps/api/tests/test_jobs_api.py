from fastapi.testclient import TestClient

from cleansolve_api.main import app


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
