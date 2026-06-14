from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from cleansolve_api.artifacts import LocalArtifactStore
from cleansolve_api.main import app
from cleansolve_api.routes import jobs
from cleansolve_api.settings import Settings

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 16


@pytest.fixture(autouse=True)
def isolated_storage_root(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")


def upload_required_images(client: TestClient, job_id: str):
    client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )
    client.post(
        f"/jobs/{job_id}/images/teacher-solution",
        files={"file": ("teacher.jpg", JPEG_BYTES, "image/jpeg")},
    )


def assert_error(response, code: str):
    payload = response.json()
    assert payload["detail"]["code"] == code
    assert isinstance(payload["detail"]["message"], str)
    assert isinstance(payload["detail"]["fields"], dict)


def test_create_job_initializes_manifest_backed_response():
    client = TestClient(app)

    response = client.post("/jobs")

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_id"].startswith("job_")
    assert payload["status"] == "CREATED"
    assert payload["revision_attempts"] == 0
    assert payload["review_items"] == []
    assert payload["latest_image_artifact_ids"] == {
        "problem": None,
        "teacher_solution": None,
    }
    assert payload["image_artifacts"] == {
        "problem": [],
        "teacher_solution": [],
    }
    assert (jobs.settings.storage_root / payload["job_id"] / "manifest.json").exists()


def test_create_job_and_run_mock_workflow_after_required_images_uploaded():
    client = TestClient(app)

    create_response = client.post("/jobs")
    job_id = create_response.json()["job_id"]
    upload_required_images(client, job_id)
    run_response = client.post(f"/jobs/{job_id}/run")

    assert create_response.status_code == 201
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "APPROVED"
    assert run_response.json()["revision_attempts"] == 1


def test_run_requires_required_images_with_structured_error():
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    response = client.post(f"/jobs/{job_id}/run")

    assert response.status_code == 409
    assert_error(response, "MISSING_REQUIRED_IMAGES")
    assert response.json()["detail"]["fields"] == {
        "missing_roles": ["problem", "teacher_solution"],
    }


def test_review_items_endpoint_hides_internal_needs_review_items():
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")
    response = client.get(f"/jobs/{job_id}/review-items")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_get_unknown_job_returns_structured_404():
    client = TestClient(app)

    response = client.get("/jobs/job_unknown")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")
    assert response.json()["detail"]["fields"] == {"job_id": "job_unknown"}


def test_run_unknown_job_returns_structured_404():
    client = TestClient(app)

    response = client.post("/jobs/job_unknown/run")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")


def test_get_unknown_job_review_items_returns_structured_404():
    client = TestClient(app)

    response = client.get("/jobs/job_unknown/review-items")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")


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


def test_settings_load_apps_api_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / "api.env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-from-env-file",
                "OPENAI_MODEL_ANALYSIS=gpt-analysis-file",
                "CLEANSOLVE_STORAGE_ROOT=var/env-file-jobs",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_ANALYSIS", raising=False)
    monkeypatch.delenv("CLEANSOLVE_STORAGE_ROOT", raising=False)
    monkeypatch.setenv("CLEANSOLVE_API_ENV_FILE", str(env_file))

    settings = Settings()

    assert settings.openai_api_key == "sk-from-env-file"
    assert settings.openai_model_analysis == "gpt-analysis-file"
    assert settings.storage_root == Path("var/env-file-jobs")


def test_manifest_store_rejects_invalid_workflow_status(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()

    with pytest.raises(ValidationError):
        store.update_after_run(
            job_id=manifest.job_id,
            status_value="INVALID",
            revision_attempts=1,
            review_items=[],
        )

    assert store.get_job(manifest.job_id).status == "CREATED"
