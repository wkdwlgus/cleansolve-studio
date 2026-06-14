from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from cleansolve_api.main import app
from cleansolve_api.routes import jobs

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 16
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024


@pytest.fixture(autouse=True)
def isolated_storage_root(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")


def create_job(client: TestClient) -> str:
    return client.post("/jobs").json()["job_id"]


def manifest_path(job_id: str):
    return jobs.settings.storage_root / job_id / "manifest.json"


def artifact_path(job_id: str, relative_path: str):
    return jobs.settings.storage_root / job_id / relative_path


def assert_error(response, code: str):
    payload = response.json()
    assert payload["detail"]["code"] == code
    assert isinstance(payload["detail"]["message"], str)
    assert isinstance(payload["detail"]["fields"], dict)


def test_upload_problem_png_persists_artifact_and_manifest():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("private-problem-name.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    artifact = payload["artifact"]
    assert payload["job_id"] == job_id
    assert payload["role"] == "problem"
    assert artifact["artifact_id"].startswith("img_")
    assert artifact["role"] == "problem"
    assert artifact["mime_type"] == "image/png"
    assert artifact["extension"] == "png"
    assert artifact["size_bytes"] == len(PNG_BYTES)
    assert artifact["sha256"] == sha256(PNG_BYTES).hexdigest()
    assert artifact["relative_path"].startswith("artifacts/images/problem/")
    assert artifact["relative_path"].endswith(".png")
    assert artifact_path(job_id, artifact["relative_path"]).read_bytes() == PNG_BYTES
    assert payload["latest_image_artifact_ids"]["problem"] == artifact["artifact_id"]
    assert manifest_path(job_id).exists()


def test_upload_teacher_solution_jpeg_persists_artifact_and_manifest():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/teacher-solution",
        files={"file": ("teacher.jpg", JPEG_BYTES, "image/jpeg")},
    )

    assert response.status_code == 201
    payload = response.json()
    artifact = payload["artifact"]
    assert payload["role"] == "teacher_solution"
    assert artifact["role"] == "teacher_solution"
    assert artifact["mime_type"] == "image/jpeg"
    assert artifact["extension"] == "jpg"
    assert artifact["relative_path"].startswith("artifacts/images/teacher_solution/")
    assert artifact["relative_path"].endswith(".jpg")
    assert artifact_path(job_id, artifact["relative_path"]).read_bytes() == JPEG_BYTES
    assert payload["latest_image_artifact_ids"]["teacher_solution"] == artifact["artifact_id"]


def test_reupload_same_role_appends_artifact_without_overwriting_previous_file():
    client = TestClient(app)
    job_id = create_job(client)

    first_response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("first.png", PNG_BYTES, "image/png")},
    )
    second_bytes = b"\x89PNG\r\n\x1a\n" + b"\x01" * 16
    second_response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("second.png", second_bytes, "image/png")},
    )

    first_artifact = first_response.json()["artifact"]
    second_artifact = second_response.json()["artifact"]
    job = client.get(f"/jobs/{job_id}").json()
    problem_artifacts = job["image_artifacts"]["problem"]

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert len(problem_artifacts) == 2
    assert [artifact["artifact_id"] for artifact in problem_artifacts] == [
        first_artifact["artifact_id"],
        second_artifact["artifact_id"],
    ]
    assert artifact_path(job_id, first_artifact["relative_path"]).exists()
    assert artifact_path(job_id, second_artifact["relative_path"]).exists()
    assert job["latest_image_artifact_ids"]["problem"] == second_artifact["artifact_id"]


def test_upload_unknown_job_returns_structured_404():
    client = TestClient(app)

    response = client.post(
        "/jobs/job_unknown/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")
    assert response.json()["detail"]["fields"] == {"job_id": "job_unknown"}


def test_upload_rejects_unsupported_mime_type():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.gif", PNG_BYTES, "image/gif")},
    )

    assert response.status_code == 415
    assert_error(response, "UNSUPPORTED_IMAGE_TYPE")
    assert response.json()["detail"]["fields"] == {
        "allowed": ["image/jpeg", "image/png"],
        "received": "image/gif",
    }


def test_upload_rejects_mime_magic_mismatch():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.png", JPEG_BYTES, "image/png")},
    )

    assert response.status_code == 400
    assert_error(response, "INVALID_IMAGE_BYTES")
    assert response.json()["detail"]["fields"] == {"reason": "mime_magic_mismatch"}


def test_upload_rejects_empty_file():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("empty.png", b"", "image/png")},
    )

    assert response.status_code == 400
    assert_error(response, "EMPTY_IMAGE")


def test_upload_rejects_oversized_file():
    client = TestClient(app)
    job_id = create_job(client)
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_IMAGE_UPLOAD_BYTES

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("large.png", oversized, "image/png")},
    )

    assert response.status_code == 413
    assert_error(response, "IMAGE_TOO_LARGE")
    assert response.json()["detail"]["fields"] == {
        "max_size_bytes": MAX_IMAGE_UPLOAD_BYTES,
    }


def test_job_response_does_not_expose_absolute_paths_or_original_filename():
    client = TestClient(app)
    job_id = create_job(client)

    client.post(
        f"/jobs/{job_id}/images/teacher-solution",
        files={"file": ("teacher-private-name.png", PNG_BYTES, "image/png")},
    )
    payload_text = client.get(f"/jobs/{job_id}").text

    assert "/Users/" not in payload_text
    assert str(jobs.settings.storage_root) not in payload_text
    assert "teacher-private-name" not in payload_text


def test_run_requires_both_problem_and_teacher_solution_images():
    client = TestClient(app)
    job_id = create_job(client)
    client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )

    response = client.post(f"/jobs/{job_id}/run")

    assert response.status_code == 409
    assert_error(response, "MISSING_REQUIRED_IMAGES")
    assert response.json()["detail"]["fields"] == {
        "missing_roles": ["teacher_solution"],
    }


def test_run_succeeds_after_both_required_images_are_uploaded():
    client = TestClient(app)
    job_id = create_job(client)
    client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )
    client.post(
        f"/jobs/{job_id}/images/teacher-solution",
        files={"file": ("teacher.jpg", JPEG_BYTES, "image/jpeg")},
    )

    response = client.post(f"/jobs/{job_id}/run")

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert response.json()["revision_attempts"] == 1
